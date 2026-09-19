import React, { useState, useEffect, useRef } from 'react';
import { SplashScreen } from './views/SplashScreen';
import { IntroScreen } from './views/IntroScreen';
import { AuthScreen } from './views/AuthScreen';
import { AuthActionHandler } from './views/AuthActionHandler';
import { AskLegalLensPage } from './views/AskLegalLensPage';
import { SettingsPage } from './views/SettingsPage';

import { Sidebar, NavView, ChatSession } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { UploadModal } from './components/upload/UploadModal';
import { documentService } from './services/documentService';
import { authService } from './services/authService';
import { auth } from './lib/firebase';
import { LegalDocument, UserProfile } from './types';

type AppStage = 'splash' | 'intro' | 'auth' | 'workspace';

const STAGE_KEY = 'legallens-app-stage';
const USER_KEY = 'legallens-user';

function loadStoredStage(): AppStage {
  try {
    const saved = sessionStorage.getItem(STAGE_KEY);
    // Resume directly into the workspace after a reload so an upload (or any
    // remount) never throws the user back to the beginning.
    if (saved === 'workspace' || saved === 'auth' || saved === 'intro') return saved;
  } catch {
    // Storage unavailable; fall through to splash.
  }
  return 'splash';
}

function loadStoredUser(): UserProfile | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    if (raw) return JSON.parse(raw) as UserProfile;
  } catch {
    // Corrupt entry; ignore.
  }
  return null;
}

export default function App() {
  const [appStage, setAppStage] = useState<AppStage>(loadStoredStage);
  const [authMode, setAuthMode] = useState<'login' | 'signup' | 'forgot'>('login');
  const [currentView, setCurrentView] = useState<NavView>('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  // Firebase action-code links (email verify / password reset) arrive at the
  // app's origin with ?mode=...&oobCode=... because we send them handleCodeInApp.
  const [authAction, setAuthAction] = useState<{ mode: 'verifyEmail' | 'resetPassword'; oobCode: string } | null>(() =>
    (() => {
      try {
        const params = new URLSearchParams(window.location.search);
        const mode = params.get('mode');
        const oobCode = params.get('oobCode');
        if ((mode === 'verifyEmail' || mode === 'resetPassword') && oobCode) {
          return { mode, oobCode };
        }
      } catch { /* ignore */ }
      return null;
    })()
  );

  const [currentUser, setCurrentUser] = useState<UserProfile>(() => loadStoredUser() || {
    id: '',
    name: '',
    email: '',
    role: 'Legal Lens User',
    plan: 'Pro Edition',
    organization: ''
  });

  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<LegalDocument | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | undefined>(undefined);

  // Tracks whether a restored session should bypass the intro/auth flow
  const sessionRestoredRef = useRef(false);
  // True when we resumed from a stored session; used to detect stale resumes.
  const resumedStoredRef = useRef(loadStoredStage() === 'workspace');
  // Fires once onAuthStateChanged resolves (session restored or signed out).
  // Gate data fetches on this so we never query with a still-loading session.
  const [authReady, setAuthReady] = useState(false);

  // Persist stage + user so a reload/resume never restarts from the beginning.
  useEffect(() => {
    try {
      sessionStorage.setItem(STAGE_KEY, appStage);
    } catch {
      // Storage unavailable; ignore.
    }
  }, [appStage]);

  useEffect(() => {
    try {
      if (currentUser && currentUser.email) {
        sessionStorage.setItem(USER_KEY, JSON.stringify(currentUser));
      } else {
        sessionStorage.removeItem(USER_KEY);
      }
    } catch {
      // Storage unavailable; ignore.
    }
  }, [currentUser]);

  // Restore an existing Firebase session on load (auto-login for returning users)
  useEffect(() => {
    const unsubscribe = authService.onAuthStateChanged((user) => {
      if (user) {
        // Gate: email/password accounts that have NOT verified their email
        // must never auto-enter the workspace. onAuthStateChanged fires
        // during signup/login BEFORE the AuthScreen's own verification check,
        // so without this a fresh user lands in the app unverified.
        const isUnverifiedPassword = user.emailVerified === false && user.provider === 'password';
        if (isUnverifiedPassword) {
          // Stay out of workspace; reset any stale restored session. The
          // AuthScreen login/signup flow performs the real sign-out.
          sessionRestoredRef.current = false;
          resumedStoredRef.current = false;
          try {
            sessionStorage.removeItem(STAGE_KEY);
            sessionStorage.removeItem(USER_KEY);
          } catch { /* ignore */ }
          setCurrentUser({ id: '', name: '', email: '', role: 'Legal Lens User', plan: 'Pro Edition', organization: '' });
          setAppStage('auth');
          return;
        }
        sessionRestoredRef.current = true;
        resumedStoredRef.current = false;
        setCurrentUser(user);
        setAppStage('workspace');
        setCurrentView('chat');
        // Auth is now restored; load documents with a valid token. This is a
        // different trigger than the email/id effect below: on a hard refresh
        // that effect fired with the storage-restored user (no token yet, 401),
        // and when the SAME user re-resolves here its deps don't change.
        refreshDocuments();
      } else if (resumedStoredRef.current) {
        // Resumed workspace from storage but Firebase has no valid session
        // (signed out elsewhere / expired) -> fall back to intro, not splash.
        resumedStoredRef.current = false;
        setAppStage('intro');
      }
    });
    return unsubscribe;
  }, []);

  // Load persistent user documents (user-level, survives chat switches & logins).
  // NOTE: waits for a real Firebase session first. On a hard refresh the stored
  // session (sessionStorage) is available instantly but app-level Firebase auth
  // restores asynchronously — firing this before a token exists guarantees a
  // 401 and an empty document list that never gets re-fetched.
  const refreshDocuments = async () => {
    try {
      if (!auth.currentUser) return;
      await auth.currentUser.getIdToken();
      const docs = await documentService.getDocuments();
      setDocuments(docs);
      if (docs.length > 0) {
        setSelectedDocument((prev) => prev || docs[0]);
      }
    } catch {
      // Backend not running - keep empty
    }
  };

  useEffect(() => {
    refreshDocuments();
  }, []);

  // Track last_uid to detect account switches (different email/Google on same browser)
  const lastUidRef = useRef<string>('');
  // Reload when authenticated user changes (login / session restore) and sync chats
  useEffect(() => {
    if (currentUser.email) {
      const uid = currentUser.id || currentUser.email;
      // Account switch: wipe previous user's docs/chats/selection first
      if (lastUidRef.current && lastUidRef.current !== uid) {
        setDocuments([]);
        setSelectedDocument(null);
        setChatSessions([]);
        setActiveChatId(undefined);
        import('./views/AskLegalLensPage').then(({ clearTranscriptCache }) => {
          try { clearTranscriptCache(); } catch { /* ignore */ }
        });
      }
      lastUidRef.current = uid;
      refreshDocuments();
      // Also sync chat history from backend (Chats are per-user, documents are not Chat-local)
      import('./services/chatService').then(({ chatService }) => {
        chatService.listConversations().then((convos) => {
          if (convos.length > 0 && chatSessions.length === 0) {
            const mapped: ChatSession[] = convos.slice(0, 20).map((c) => ({
              id: c.conversation_id,
              documentId: c.document_id || undefined,
              conversationId: c.conversation_id,
              title: c.preview ? c.preview.slice(0, 40) : (c.document_id ? `Chat: ${c.document_id}` : 'LegalLens Chat'),
              updatedAt: 'Just now',
              timeframe: 'Today',
            }));
            setChatSessions(mapped);
            if (!activeChatId && mapped.length > 0) setActiveChatId(mapped[0].id);
          }
        });
      });
    }
  }, [currentUser.email, currentUser.id]);

  const handleSelectDocument = (doc: LegalDocument) => {
    setSelectedDocument(doc);
    // Create new chat session for selected document
    const newChat: ChatSession = {
      id: `chat-${Date.now()}`,
      documentId: doc.id,
      title: `Analysis: ${doc.name}`,
      updatedAt: 'Just now',
      timeframe: 'Today'
    };
    setChatSessions((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
  };

  const handleDeleteDocument = async (id: string) => {
    const didDelete = await documentService.deleteDocument(id);
    if (!didDelete) return;
    const updated = documents.filter((d) => d.id !== id);
    setDocuments(updated);
    if (selectedDocument?.id === id) {
      setSelectedDocument(updated.length > 0 ? updated[0] : null);
    }
  };

  const handleUploadComplete = (newDoc: LegalDocument) => {
    setDocuments((prev) => [newDoc, ...prev]);
    setSelectedDocument(newDoc);
    setCurrentView('chat');

    const newChat: ChatSession = {
      id: `chat-${Date.now()}`,
      documentId: newDoc.id,
      title: `Uploaded: ${newDoc.name}`,
      updatedAt: 'Just now',
      timeframe: 'Today'
    };
    setChatSessions((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
  };

  const handleNewChat = () => {
    const newChat: ChatSession = {
      id: `chat-${Date.now()}`,
      documentId: selectedDocument?.id,
      title: selectedDocument ? `Chat: ${selectedDocument.name}` : 'New LegalLens Chat',
      updatedAt: 'Just now',
      timeframe: 'Today'
    };
    setChatSessions((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    setCurrentView('chat');
  };

  const handleSelectChat = (id: string) => {
    const session = chatSessions.find((c) => c.id === id);
    if (session?.documentId) {
      const doc = documents.find((d) => d.id === session.documentId);
      if (doc) setSelectedDocument(doc);
    }
    setActiveChatId(id);
    setCurrentView('chat');
  };

  const handleConversationChange = (conversationId: string) => {
    if (!activeChatId) return;
    setChatSessions((prev) =>
      prev.map((c) => (c.id === activeChatId ? { ...c, conversationId } : c))
    );
  };

  const activeSession = chatSessions.find((c) => c.id === activeChatId);

  const handleSignOut = async () => {
    await authService.logout();
    try {
      sessionStorage.removeItem(STAGE_KEY);
      sessionStorage.removeItem(USER_KEY);
    } catch {
      // Storage unavailable; ignore.
    }
    // Clear in-memory state so next login starts fresh and then reloads from backend
    // Also clear chat transcript cache to prevent leaking prior user's messages
    try {
      const { clearTranscriptCache } = await import('./views/AskLegalLensPage');
      clearTranscriptCache();
    } catch { /* ignore */ }
    setDocuments([]);
    setSelectedDocument(null);
    setChatSessions([]);
    setActiveChatId(undefined);
    setCurrentUser({ id: '', name: '', email: '', role: 'Legal Lens User', plan: 'Pro Edition', organization: '' });
    resumedStoredRef.current = false;
    setAppStage('intro');
  };

  // Render Splash Screen
  if (authAction) {
    return (
      <AuthActionHandler
        mode={authAction.mode}
        oobCode={authAction.oobCode}
        onComplete={() => {
          try {
            const url = new URL(window.location.href);
            url.searchParams.delete('mode');
            url.searchParams.delete('oobCode');
            url.searchParams.delete('apiKey');
            url.searchParams.delete('lang');
            url.searchParams.delete('continueUrl');
            window.history.replaceState({}, '', url.toString());
          } catch { /* ignore */ }
          setAuthAction(null);
          setAuthMode('login');
          resumedStoredRef.current = false;
          setAppStage('auth');
        }}
      />
    );
  }

  // Render Splash Screen
  if (appStage === 'splash') {
    return (
      <SplashScreen
        onComplete={() => {
          if (sessionRestoredRef.current) {
            setAppStage('workspace');
          } else {
            setAppStage('intro');
          }
        }}
      />
    );
  }

  // Render Intro Landing Page
  if (appStage === 'intro') {
    return (
      <IntroScreen
        onGetStarted={() => {
          setAuthMode('signup');
          setAppStage('auth');
        }}
        onLogin={() => {
          setAuthMode('login');
          setAppStage('auth');
        }}
      />
    );
  }

  // Render Auth Screen (Login/Signup/Forgot)
  if (appStage === 'auth') {
    return (
      <AuthScreen
        initialMode={authMode}
        onSuccess={(user) => {
          setCurrentUser(user);
          setAppStage('workspace');
          setCurrentView('chat');
        }}
        onBackToIntro={() => setAppStage('intro')}
      />
    );
  }

  // Render Main Workspace Shell (ChatGPT Style Interface)
  return (
    <div id="legallens-app-root" className="min-h-screen bg-[#05070c] text-slate-100 flex flex-col selection:bg-indigo-500/30">
      <div className="flex-1 flex overflow-hidden">
        {/* Simplified ChatGPT-style Sidebar */}
        <Sidebar
          currentView={currentView}
          onNavigate={(view) => {
            setCurrentView(view);
            setIsMobileMenuOpen(false);
          }}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onSignOut={handleSignOut}
          onOpenUpload={() => setIsUploadModalOpen(true)}
          documents={documents}
          selectedDocument={selectedDocument}
          onSelectDocument={handleSelectDocument}
          onDeleteDocument={handleDeleteDocument}
          chatSessions={chatSessions}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
          user={currentUser}
          isMobileOpen={isMobileMenuOpen}
          onCloseMobile={() => setIsMobileMenuOpen(false)}
        />

        {/* Main Workspace Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Topbar Header */}
          <Topbar
            user={currentUser}
            activeDocument={selectedDocument}
            allDocuments={documents}
            onSelectDocument={handleSelectDocument}
            onOpenUpload={() => setIsUploadModalOpen(true)}
            onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
            onNavigateToSettings={() => setCurrentView('settings')}
            onSelectView={(v) => setCurrentView(v)}
            onSignOut={handleSignOut}
          />

          {/* Active View Container */}
          <main className="flex-1 overflow-hidden bg-gradient-to-b from-[#05070c] via-[#070a12] to-[#05070c]">
            {currentView === 'chat' && (
              <AskLegalLensPage
                document={selectedDocument}
                user={currentUser}
                onOpenUpload={() => setIsUploadModalOpen(true)}
                chatKey={activeChatId}
                conversationSeed={activeSession?.conversationId}
                onConversationChange={handleConversationChange}
              />
            )}

            {currentView === 'settings' && (
              <div className="p-6 overflow-y-auto max-h-[calc(100vh-4rem)]">
                <SettingsPage
                  user={currentUser}
                  onUpdateUser={setCurrentUser}
                />
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Document Upload Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadComplete={handleUploadComplete}
      />
    </div>
  );
}
