import React, { useState } from 'react';
import { 
  Plus, 
  FileText, 
  MessageSquareText, 
  Settings, 
  LogOut, 
  ChevronLeft, 
  ChevronRight,
  Upload,
  Trash2,
  Sparkles,
  Clock,
  User as UserIcon,
  ShieldCheck
} from 'lucide-react';
import { Logo } from '../brand/Logo';
import { LegalDocument, UserProfile } from '../../types';

export type NavView = 'chat' | 'settings';

export interface ChatSession {
  id: string;
  documentId?: string;
  conversationId?: string;
  title: string;
  updatedAt: string;
  timeframe: 'Today' | 'Yesterday' | 'Previous 7 Days' | 'Older';
}

interface SidebarProps {
  currentView: NavView;
  onNavigate: (view: NavView) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onSignOut: () => void;
  onOpenUpload: () => void;
  documents: LegalDocument[];
  selectedDocument: LegalDocument | null;
  onSelectDocument: (doc: LegalDocument) => void;
  onDeleteDocument: (docId: string) => void;
  chatSessions: ChatSession[];
  activeChatId?: string;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  user: UserProfile;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onNavigate,
  isCollapsed,
  onToggleCollapse,
  onSignOut,
  onOpenUpload,
  documents,
  selectedDocument,
  onSelectDocument,
  onDeleteDocument,
  chatSessions,
  activeChatId,
  onSelectChat,
  onNewChat,
  user,
  isMobileOpen = false,
  onCloseMobile
}) => {
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleNavClick = (view: NavView) => {
    onNavigate(view);
    if (onCloseMobile) onCloseMobile();
  };

  // Group chats by timeframe
  const timeframes: ('Today' | 'Yesterday' | 'Previous 7 Days' | 'Older')[] = [
    'Today',
    'Yesterday',
    'Previous 7 Days',
    'Older'
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-40 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar Container */}
      <aside
        id="legallens-sidebar"
        className={`fixed lg:static top-0 bottom-0 left-0 z-40 flex flex-col justify-between bg-[#080b11] border-r border-slate-800/80 transition-all duration-300 select-none ${
          isCollapsed ? 'w-20' : 'w-64'
        } ${isMobileOpen ? 'translate-x-0 w-64' : '-translate-x-full lg:translate-x-0'}`}
      >
        {/* Top Branding & New Chat Action */}
        <div className="p-4 border-b border-slate-800/70 space-y-3">
          <div className="flex items-center justify-between">
            <Logo
              size={isCollapsed ? 'xs' : 'sm'}
              showText={!isCollapsed}
              onClick={() => handleNavClick('chat')}
            />

            {/* Collapse toggle (Desktop only) */}
            <button
              onClick={onToggleCollapse}
              className="hidden lg:flex p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-expanded={!isCollapsed}
            >
              {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          </div>

          {/* Primary Action: + New Chat */}
          {!isCollapsed ? (
            <button
              onClick={() => {
                onNewChat();
                if (onCloseMobile) onCloseMobile();
              }}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-xs font-bold shadow-lg shadow-indigo-500/20 transition-all cursor-pointer hover-float-sm"
            >
              <Plus className="w-4 h-4" />
              <span>New Chat</span>
            </button>
          ) : (
            <button
              onClick={() => {
                onNewChat();
                if (onCloseMobile) onCloseMobile();
              }}
              className="w-full flex items-center justify-center p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white shadow-md cursor-pointer"
              title="New Chat"
              aria-label="New Chat"
            >
              <Plus className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Scrollable Navigation Sections */}
        <div className="flex-1 py-3 px-3 space-y-5 overflow-y-auto custom-scrollbar">
          {/* Section 1: Uploaded Documents */}
          <div>
            {!isCollapsed && (
              <div className="flex items-center justify-between px-2 mb-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">
                  Uploaded Documents
                </span>
                <button
                  onClick={onOpenUpload}
                  className="p-1 rounded text-slate-400 hover:text-indigo-300 hover:bg-slate-800/80 transition-colors"
                  title="Upload New Document"
                  aria-label="Upload New Document"
                >
                  <Upload className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            <div className="space-y-1">
              {documents.map((doc) => {
                const isSelected = selectedDocument?.id === doc.id;
                const status = (doc as any).indexingStatus || (doc.analysisStatus === 'Processing' ? 'indexing' : 'indexed');
                const statusLabel = status === 'indexed' ? 'Indexed' : status === 'indexing' ? 'Indexing...' : status === 'indexing_failed' ? 'Failed' : status;
                const statusColor = status === 'indexed' ? 'text-emerald-400' : status === 'indexing' ? 'text-amber-400' : 'text-rose-400';
                return (
                  <div
                    key={doc.id}
                    role="button"
                    tabIndex={0}
                    aria-current={isSelected ? 'true' : undefined}
                    aria-label={
                      isCollapsed
                        ? `${doc.name} — ${statusLabel}`
                        : `${doc.name}, ${statusLabel}`
                    }
                    className={`group relative flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-600/20 text-white border border-indigo-500/50 font-medium'
                        : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                    }`}
                    onClick={() => {
                      onSelectDocument(doc);
                      onNavigate('chat');
                      if (onCloseMobile) onCloseMobile();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onSelectDocument(doc);
                        onNavigate('chat');
                        if (onCloseMobile) onCloseMobile();
                      }
                    }}
                    title={isCollapsed ? `${doc.name} · ${statusLabel}` : undefined}
                  >
                    <FileText className={`w-4 h-4 shrink-0 ${isSelected ? 'text-indigo-400' : 'text-slate-400 group-hover:text-slate-200'}`} />
                    
                    {!isCollapsed && (
                      <span className="flex-1 truncate text-left">
                        <span className="block truncate">{doc.name}</span>
                        <span className={`text-[10px] font-mono ${statusColor}`}>{statusLabel}</span>
                      </span>
                    )}

                    {!isCollapsed && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteDocument(doc.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 rounded transition-opacity"
                        title="Delete Document"
                        aria-label={`Delete ${doc.name}`}
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                );
              })}

              {documents.length === 0 && !isCollapsed && (
                <div
                  onClick={onOpenUpload}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onOpenUpload();
                    }
                  }}
                  className="p-3 rounded-xl border border-dashed border-slate-800 hover:border-indigo-500/40 text-center text-xs text-slate-500 hover:text-indigo-300 cursor-pointer transition-colors"
                >
                  + Upload your first document
                </div>
              )}
            </div>
          </div>

          {/* Section 2: Chats */}
          <div>
            {!isCollapsed && (
              <div className="px-2 mb-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">
                  Chats
                </span>
              </div>
            )}

            <div className="space-y-1">
              {chatSessions.map((chat) => {
                const isActive = activeChatId === chat.id;
                return (
                  <button
                    key={chat.id}
                    onClick={() => {
                      onSelectChat(chat.id);
                      onNavigate('chat');
                      if (onCloseMobile) onCloseMobile();
                    }}
                    aria-current={isActive ? 'true' : undefined}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-all text-left truncate ${
                      isActive
                        ? 'bg-slate-800 text-white font-medium border border-slate-700'
                        : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                    }`}
                    title={isCollapsed ? chat.title : undefined}
                  >
                    <MessageSquareText className="w-3.5 h-3.5 shrink-0 text-slate-500" />
                    {!isCollapsed && (
                      <span className="flex-1 truncate">{chat.title}</span>
                    )}
                  </button>
                );
              })}

              {chatSessions.length === 0 && !isCollapsed && (
                <div className="px-3 py-2 text-xs text-slate-500 italic">
                  No previous conversations
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom User Profile Section */}
        <div className="p-3 border-t border-slate-800/70 relative">
          <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800/60 transition-colors">
            <div 
              className="flex items-center gap-2.5 min-w-0 cursor-pointer"
              onClick={() => setShowUserMenu(!showUserMenu)}
            >
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-sm">
                {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
              </div>
              {!isCollapsed && (
                <div className="min-w-0 text-left">
                  <div className="text-xs font-semibold text-white truncate">
                    {user?.name || 'Legal Lens User'}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">
                    {user?.email || 'user@legallens.ai'}
                  </div>
                </div>
              )}
            </div>

            {!isCollapsed && (
              <button
                onClick={onSignOut}
                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};

