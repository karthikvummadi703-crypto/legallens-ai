import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquareText, 
  Send, 
  Sparkles, 
  User, 
  Bot, 
  Copy, 
  Check, 
  FileText, 
  ExternalLink, 
  CornerDownRight, 
  HelpCircle,
  Loader2,
  RefreshCw,
  ShieldCheck,
  ArrowRight,
  AlertTriangle,
  Calendar,
  DollarSign,
  CheckSquare,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  Upload
} from 'lucide-react';
import { LegalDocument, ChatMessage, SourceReference, FullAnalysisResponse, UserProfile } from '../types';
import { chatService } from '../services/chatService';
import { analysisService } from '../services/analysisService';
import { Button } from '../components/ui/Button';

interface AskLegalLensPageProps {
  document?: LegalDocument | null;
  onNavigateToClause?: (ref: string) => void;
  onOpenUpload?: () => void;
  user?: UserProfile;
  chatKey?: string;
  conversationSeed?: string;
  onConversationChange?: (conversationId: string) => void;
}

// Chat transcript cache: survives component remounts (modal open/close, doc
// switches, view toggles) so an ongoing conversation never resets to the
// beginning. Backend history remains the source of truth on cold starts.
const transcriptCache = new Map<string, ChatMessage[]>();

export function clearTranscriptCache() {
  transcriptCache.clear();
}

function transcriptKey(chatKey?: string, docId?: string | null, seed?: string, userId?: string | null): string {
  return `${userId || 'nouser'}::${chatKey || 'default'}::${docId || 'none'}::${seed || 'fresh'}`;
}

export const AskLegalLensPage: React.FC<AskLegalLensPageProps> = ({
  document,
  onNavigateToClause,
  onOpenUpload,
  user,
  chatKey,
  conversationSeed,
  onConversationChange
}) => {
  const userId = user?.id || user?.email || null;
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    transcriptCache.get(transcriptKey(chatKey, document?.id, conversationSeed, userId)) || []
  );
  const [inputQuery, setInputQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<SourceReference | null>(null);
  const [analysisData, setAnalysisData] = useState<FullAnalysisResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [lastFailedQuery, setLastFailedQuery] = useState<string | null>(null);
  
  // Interactive checklist state for "Before You Sign"
  const [checklistState, setChecklistState] = useState<Record<string, boolean>>({});

  const userName = user?.name ? user.name.split(' ')[0] : 'there';

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Live transcript length for this mounted chat (updated by the cache
  // effect below). Used to detect a mid-session conversationSeed bind so we
  // never re-restore (and clobber) a transcript that is already on screen.
  const messagesLenRef = useRef<number>(messages.length);

  // Tracks the previous mount effect inputs across re-renders.
  const prevSeedRef = useRef<string | undefined>(conversationSeed);
  const prevDocRef = useRef<string | null | undefined>(document?.id);
  const prevChatKeyRef = useRef<string | undefined>(chatKey);

  useEffect(() => {
    // Capture inputs once for this run and advance the refs immediately so
    // every return path below stays consistent.
    const effectSeed = conversationSeed;
    const effectDoc = document?.id;
    const effectChat = chatKey;
    const seedBoundMidChat =
      !!effectSeed &&
      prevSeedRef.current !== effectSeed &&
      prevDocRef.current === effectDoc &&
      prevChatKeyRef.current === effectChat &&
      messagesLenRef.current > 0;
    prevSeedRef.current = effectSeed;
    prevDocRef.current = effectDoc;
    prevChatKeyRef.current = effectChat;

    // Serve the cached transcript instantly on remount; it is identical to
    // what the restore below would fetch, so skip the network round-trip.
    // Key includes userId so different emails/Google accounts never share cache.
    const key = transcriptKey(chatKey, document?.id, conversationSeed, userId);
    const cached = transcriptCache.get(key);
    if (cached && cached.length > 0) {
      setMessages(cached);
      if (conversationSeed) setConversationId(conversationSeed);
      return;
    }
    // Mid-chat conversationSeed bind (first reply just assigned the backend
    // conversationId): the on-screen transcript is already correct — adopt
    // the seed without re-restoring from the server (which could wipe an
    // in-flight second message).
    if (seedBoundMidChat) {
      setConversationId(effectSeed);
      setAnalysisData(null);
      return;
    }
    // ChatGPT-style: conversationId is the source of truth for history;
    // document selection is just context, not ownership. Keep conversation
    // across document switches so cross-chat doc retrieval works naturally.
    // Only reset when chatKey (frontend chat session) changes.
    setAnalysisData(null);

    if (conversationSeed) {
      // Restore backend history for this chat session (works for both
      // document-scoped and library-wide conversations)
      const restore = async () => {
        // Try general history first (unified stores with document_id=None or selected)
        const h = await chatService.getGeneralHistory(conversationSeed);
        if (h.messages.length > 0) {
          setMessages(h.messages);
          if (h.conversationId) setConversationId(h.conversationId);
          return;
        }
        // Fallback: try document-scoped history if we have a selected doc
        if (document?.id) {
          const msgs = await chatService.getInitialMessages(document.id, conversationSeed);
          if (msgs.length > 0) {
            setMessages(msgs);
            setConversationId(conversationSeed);
          }
        }
      };
      restore();
      // Fetch analysis if doc selected
      if (document?.id) {
        analysisService.getAnalysis(document.id).then((res) => {
          if (res) setAnalysisData(res);
        });
      }
      return;
    }

    // No conversationSeed: fresh chat
    setConversationId(undefined);
    if (!document?.id) {
      setMessages([]);
      return;
    }
    // Fresh doc chat with no history -> welcome message + analysis preload
    setMessages([
      {
        id: 'msg-welcome-user',
        sender: 'assistant',
        text: `Hello ${user?.name || 'there'}! I am LegalLens AI, your document intelligence assistant. Ask me anything about **${document.name}**, or click 'Analyze Document' for a full breakdown.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        suggestedFollowUps: [
          'Give me a complete analysis of this document.',
          'What are the biggest risks?',
          'What are my payment deadlines?'
        ]
      }
    ]);
    analysisService.getAnalysis(document.id).then((res) => {
      if (res) setAnalysisData(res);
    });
  }, [document?.id, chatKey, conversationSeed]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Persist every transcript update so remounts restore instantly.
  useEffect(() => {
    messagesLenRef.current = messages.length;
    transcriptCache.set(transcriptKey(chatKey, document?.id, conversationSeed, userId), messages);
  }, [messages, chatKey, document?.id, conversationSeed, userId]);

  const isGeneralChat = !document;
  const docName = document?.name ?? 'LegalLens AI Assistant';
  const docId = document?.id ?? null;

  const suggestedPrompts = [
    { title: 'Full Analysis', query: 'Give me a complete analysis of this document.' },
    { title: 'Potential Risks', query: 'What could put me at risk in this contract?' },
    { title: 'My Obligations', query: 'What are my responsibilities and obligations?' },
    { title: 'Payment Terms', query: 'What payments am I responsible for?' },
    { title: 'Important Dates', query: 'What deadlines and key dates should I know?' },
    { title: 'Termination & Renewal', query: 'When can this contract be terminated and does it renew?' },
    { title: 'Before You Sign', query: 'What should I check before signing this contract?' },
    { title: 'Lawyer Questions', query: 'What questions should I ask a lawyer about this?' }
  ];

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText || inputQuery).trim();
    if (!textToSend || isTyping || isAnalyzing) return;
    // Guard: doc indexing still in progress
    if (document && (document as any).indexingStatus === 'indexing') {
      const waitMsg: ChatMessage = {
        id: `msg-wait-${Date.now()}`,
        sender: 'assistant',
        text: `Your document **${document.name}** is still being indexed. Please wait a moment and try again.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        suggestedFollowUps: ['What is a confidentiality clause?']
      };
      setMessages((prev) => [...prev, { id: `msg-${Date.now()}`, sender: 'user', text: textToSend, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } as ChatMessage, waitMsg]);
      if (!queryText) setInputQuery('');
      return;
    }

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInputQuery('');
    setIsTyping(true);
    setLastFailedQuery(null);

    try {
      // Check if user is requesting a full analysis (document mode only)
      const isAnalysisRequest =
        textToSend.toLowerCase().includes('complete analysis') ||
        textToSend.toLowerCase().includes('full analysis');

      if (docId && isAnalysisRequest) {
        let currentAnalysis = analysisData;
        if (!currentAnalysis) {
          setIsAnalyzing(true);
          currentAnalysis = await analysisService.analyzeDocument(docId);
          if (currentAnalysis) setAnalysisData(currentAnalysis);
          setIsAnalyzing(false);
        }

        const aiMsg: ChatMessage = {
          id: `msg-ai-${Date.now()}`,
          sender: 'assistant',
          text: currentAnalysis?.executive_summary?.summary 
            ? `Here is the full document analysis for **${document.name}**:`
            : `Below is the complete AI analysis of **${document.name}**:`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sources: [
            { page: 1, section: 'Executive Summary', quote: currentAnalysis?.executive_summary?.summary || 'Document overview' }
          ],
          suggestedFollowUps: [
            'What are the biggest risks?',
            'What are my payment deadlines?',
            'What should I ask a lawyer?'
          ]
        };

        setMessages((prev) => [...prev, aiMsg]);
        setIsTyping(false);
        return;
      }

      // Unified RAG API Call: supports persistent cross-chat retrieval.
      // Sends selected_document_id for context but backend resolves
      // natural references (e.g. "my employment contract") across the
      // user's full library via user-scoped Qdrant filtering.
      const result = await chatService.askUnified(
        textToSend,
        docId,
        conversationId,
        chatKey
      );
      if (result.conversationId) {
        setConversationId(result.conversationId);
        onConversationChange?.(result.conversationId);
      }

      const aiMsg: ChatMessage = {
        id: `msg-ai-${Date.now()}`,
        sender: 'assistant',
        text: result.response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: result.sources,
        suggestedFollowUps: result.followUps
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const msg = err?.message?.includes('timeout') || err?.name === 'AbortError'
        ? "The request timed out. The AI may be busy — please retry in a few seconds."
        : (err?.message || "LegalLens couldn't answer right now. Please check your connection and try again.");
      const errorMsg: ChatMessage = {
        id: `msg-err-${Date.now()}`,
        sender: 'assistant',
        text: msg,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        suggestedFollowUps: lastFailedQuery ? [] : ['Try again']
      };
      setMessages((prev) => [...prev, errorMsg]);
      setLastFailedQuery(textToSend);
    } finally {
      setIsTyping(false);
      setIsAnalyzing(false);
    }
  };

  const handleFullAnalysisClick = () => {
    handleSendMessage('Give me a complete analysis of this document.');
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleChecklistItem = (id: string) => {
    setChecklistState((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div id="ask-legallens-chat-view" className="flex flex-col h-[calc(100vh-4rem)] max-w-6xl mx-auto p-3 sm:p-6 select-none">
      {/* Top Document Workspace Header */}
      <div className="p-3 sm:p-4 rounded-2xl bg-[#090d16]/90 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0 mb-3 shadow-lg">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-md shrink-0">
            <MessageSquareText className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-white truncate">
                {isGeneralChat ? 'LegalLens AI Assistant' : 'LegalLens AI Workspace'}
              </h2>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded border font-semibold shrink-0 ${isGeneralChat ? 'bg-sky-500/20 text-sky-300 border-sky-500/30' : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'}`}>
                {isGeneralChat ? 'General AI' : 'Indexed & Grounded'}
              </span>
            </div>
            <p className="text-xs text-slate-400 truncate">
              {isGeneralChat ? (
                'No document selected — ask any general legal question.'
              ) : (
                <>
                  Selected: <span className="text-indigo-300 font-semibold">{docName}</span>
                  {(document as any)?.indexingStatus === 'indexing' && <span className="ml-2 text-amber-300">• Indexing…</span>}
                  {(document as any)?.indexingStatus === 'indexing_failed' && <span className="ml-2 text-rose-300">• Indexing failed</span>}
                </>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {!isGeneralChat && (
            <Button
              variant="glow"
              size="sm"
              onClick={handleFullAnalysisClick}
              isLoading={isAnalyzing}
              leftIcon={<Sparkles className="w-3.5 h-3.5" />}
              className="text-xs font-semibold"
            >
              Analyze Document
            </Button>
          )}
          {onOpenUpload && (
            <button
              onClick={onOpenUpload}
              className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-colors text-xs"
              title="Upload new document"
            >
              <Upload className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Chat Stream Container */}
      <div className="flex-1 rounded-2xl bg-[#080b11]/80 border border-slate-800/80 p-4 sm:p-6 overflow-y-auto space-y-6 custom-scrollbar">
        {messages.length === 0 ? (
          /* Empty Chat Welcome State */
          <div className="flex flex-col items-center justify-center min-h-full text-center p-4 sm:p-8 space-y-6">
            <div className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-500/20 to-violet-500/20 border border-indigo-500/30 text-indigo-400 shadow-xl">
              <Sparkles className="w-8 h-8 text-indigo-400 animate-pulse" />
            </div>

            <div className="space-y-2 max-w-lg">
              <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
                Understand before you sign.
              </h1>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                {isGeneralChat ? (
                  'Ask LegalLens any legal question — no document upload required. Get plain-language explanations of clauses, rights, and contract concepts.'
                ) : (
                  <>Ask LegalLens anything about <span className="text-indigo-300 font-semibold">{docName}</span>. Receive instant, grounded answers citing page numbers and section clauses.</>
                )}
              </p>
            </div>

            {/* Quick Prompt Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 w-full max-w-4xl text-left">
              {suggestedPrompts.map((sp, idx) => (
                <div
                  key={idx}
                  onClick={() => handleSendMessage(sp.query)}
                  className="p-3.5 rounded-2xl bg-slate-900/90 hover:bg-indigo-950/40 border border-slate-800 hover:border-indigo-500/40 transition-all cursor-pointer group hover-float-sm flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-indigo-300 group-hover:text-white font-mono">
                      {sp.title}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 transition-transform group-hover:translate-x-0.5" />
                  </div>
                  <p className="text-xs text-slate-400 group-hover:text-slate-300 leading-snug">
                    "{sp.query}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${
                msg.sender === 'user' ? 'ml-auto max-w-2xl flex-row-reverse' : 'mr-auto max-w-4xl'
              }`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold ${
                  msg.sender === 'user'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-slate-800 text-indigo-400 border border-slate-700'
                }`}
              >
                {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Content Container */}
              <div className="space-y-3 flex-1 min-w-0">
                <div
                  className={`p-4 sm:p-5 rounded-2xl text-xs sm:text-sm leading-relaxed ${
                    msg.sender === 'user'
                      ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-tr-none shadow-md'
                      : 'bg-[#0b0f19] text-slate-200 border border-slate-800 rounded-tl-none space-y-4 shadow-lg'
                  }`}
                >
                  {/* Main Text Content */}
                  <div className="whitespace-pre-wrap leading-relaxed">
                    {msg.text}
                  </div>

                  {/* Render Structured Cards if full analysis data exists */}
                  {msg.sender === 'assistant' && analysisData && (msg.text.includes('full document analysis') || msg.text.includes('complete AI analysis')) && (
                    <div className="space-y-4 pt-2 border-t border-slate-800/80">
                      {/* Executive Summary Card */}
                      {analysisData.executive_summary && (
                        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5">
                          <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase font-mono tracking-wider">
                            <FileText className="w-4 h-4" />
                            <span>Executive Summary</span>
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed">
                            {analysisData.executive_summary.summary}
                          </p>
                        </div>
                      )}

                      {/* Potential Concerns Card */}
                      {analysisData.potential_risks && analysisData.potential_risks.length > 0 && (
                        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase font-mono tracking-wider">
                              <AlertTriangle className="w-4 h-4" />
                              <span>Potential Concerns ({analysisData.potential_risks.length})</span>
                            </div>
                          </div>
                          <div className="space-y-2">
                            {analysisData.potential_risks.map((risk, rIdx) => (
                              <div key={rIdx} className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs space-y-1.5">
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold text-white">{risk.title}</span>
                                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                                    risk.severity === 'high' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                  }`}>
                                    {risk.severity} Risk
                                  </span>
                                </div>
                                <p className="text-slate-300 text-[11px] leading-relaxed">
                                  {risk.explanation}
                                </p>
                                <div className="text-[10px] font-mono text-indigo-400 pt-1">
                                  Source: Page {risk.page} • {risk.section}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Key Obligations Card */}
                      {analysisData.obligations && analysisData.obligations.length > 0 && (
                        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                          <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase font-mono tracking-wider">
                            <CheckSquare className="w-4 h-4" />
                            <span>Your Obligations</span>
                          </div>
                          <div className="space-y-2">
                            {analysisData.obligations.map((ob, oIdx) => (
                              <div key={oIdx} className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-xs">
                                <div className="w-5 h-5 rounded bg-indigo-500/20 text-indigo-300 font-mono font-bold flex items-center justify-center shrink-0 mt-0.5 text-[10px]">
                                  {oIdx + 1}
                                </div>
                                <div className="space-y-1 min-w-0">
                                  <div className="font-semibold text-slate-200">{ob.party}</div>
                                  <p className="text-slate-400 text-[11px] leading-relaxed">{ob.obligation}</p>
                                  {ob.deadline && (
                                    <div className="text-[10px] font-mono text-emerald-400">Deadline: {ob.deadline}</div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Payment Terms Card */}
                      {analysisData.payments && analysisData.payments.length > 0 && (
                        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                          <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase font-mono tracking-wider">
                            <DollarSign className="w-4 h-4" />
                            <span>Payment & Financial Summary</span>
                          </div>
                          <div className="space-y-2 text-xs pt-1">
                            {analysisData.payments.map((p, pIdx) => (
                              <div key={pIdx} className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 grid grid-cols-2 gap-2">
                                <div>
                                  <span className="text-[10px] text-slate-500 block">{p.item}</span>
                                  <span className="font-semibold text-slate-200">{p.amount}</span>
                                </div>
                                <div>
                                  <span className="text-[10px] text-slate-500 block">Due</span>
                                  <span className="text-slate-300">{p.due_date}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Lawyer Questions Card */}
                      {analysisData.lawyer_questions && analysisData.lawyer_questions.length > 0 && (
                        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                          <div className="flex items-center gap-2 text-purple-400 font-bold text-xs uppercase font-mono tracking-wider">
                            <HelpCircle className="w-4 h-4" />
                            <span>Questions for Your Lawyer</span>
                          </div>
                          <div className="space-y-2">
                            {analysisData.lawyer_questions.map((lq, qIdx) => (
                              <div key={qIdx} className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs space-y-1">
                                <div className="font-semibold text-indigo-300">"{lq.question}"</div>
                                <p className="text-slate-400 text-[11px] leading-relaxed">{lq.context}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Grounded Source Citations Chips */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="pt-3 border-t border-slate-800/80 space-y-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-400 block font-mono">
                        Grounded Sources in Document:
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {msg.sources.map((src, sIdx) => (
                          <button
                            key={sIdx}
                            onClick={() => setSelectedSource(src)}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-500/30 text-indigo-300 text-xs font-mono transition-colors cursor-pointer hover-float-pill"
                          >
                            <FileText className="w-3 h-3 text-indigo-400" />
                            <span>{src.document_name ? `${src.document_name} • ` : ''}Page {src.page} • {src.section}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Message Footer Actions */}
                <div className="flex items-center justify-between text-[11px] text-slate-500 px-1">
                  <span>{msg.timestamp}</span>
                  {msg.sender === 'assistant' && (
                    <button
                      onClick={() => copyToClipboard(msg.id, msg.text)}
                      className="flex items-center gap-1 text-slate-400 hover:text-white transition-colors"
                    >
                      {copiedId === msg.id ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span className="text-emerald-400">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy Response</span>
                        </>
                      )}
                    </button>
                  )}
                </div>

                {/* Suggested Follow-Ups */}
                {msg.suggestedFollowUps && msg.suggestedFollowUps.length > 0 && (
                  <div className="pt-1 flex flex-wrap gap-1.5">
                    {msg.suggestedFollowUps.map((prompt, pIdx) => (
                      <button
                        key={pIdx}
                        onClick={() => handleSendMessage(prompt)}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-indigo-500/40 text-slate-300 hover:text-indigo-300 text-xs transition-colors cursor-pointer hover-float-pill"
                      >
                        <CornerDownRight className="w-3 h-3 text-indigo-400" />
                        <span>{prompt}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {isTyping && (
          <div className="flex gap-3 items-center text-xs text-slate-400">
            <div className="w-8 h-8 rounded-xl bg-slate-800 flex items-center justify-center text-indigo-400 border border-slate-700 shrink-0">
              <Bot className="w-4 h-4 animate-spin" />
            </div>
            <div className="p-3.5 rounded-2xl bg-[#0b0f19] border border-slate-800 text-slate-400 flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
              <span>{isGeneralChat ? 'Generating legal guidance…' : 'Analyzing document context and retrieving grounded clause sources…'}</span>
            </div>
          </div>
        )}

        {lastFailedQuery && (
          <div className="flex justify-center">
            <button
              onClick={() => handleSendMessage(lastFailedQuery)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-xs font-semibold transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry: "{lastFailedQuery.slice(0, 40)}{lastFailedQuery.length > 40 ? '…' : ''}"</span>
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Query Bar */}
      <div className="py-2 flex items-center gap-2 overflow-x-auto text-xs shrink-0 custom-scrollbar">
        <span className="text-slate-500 font-mono text-[10px] uppercase font-bold whitespace-nowrap">Suggested:</span>
        {suggestedPrompts.map((sp, idx) => (
          <button
            key={idx}
            onClick={() => handleSendMessage(sp.query)}
            className="px-3 py-1 rounded-full bg-slate-900/90 hover:bg-slate-800 border border-slate-800 hover:border-indigo-500/40 text-slate-300 hover:text-white text-xs transition-colors whitespace-nowrap cursor-pointer hover-float-pill"
          >
            {sp.title}
          </button>
        ))}
      </div>

      {/* Fixed ChatGPT-Style Input Bar */}
      <div className="mt-1 shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="relative flex items-end gap-2"
        >
          <textarea
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            rows={1}
            placeholder={isGeneralChat
              ? `Ask LegalLens any legal question... (e.g. 'What is a non-compete clause?') — Enter to send, Shift+Enter for newline`
              : `Ask LegalLens about ${docName}... (e.g. 'What are the risks?', 'When is payment due?') — Enter to send, Shift+Enter for newline`}
            className="w-full min-h-[48px] max-h-[120px] py-3.5 pl-4 pr-16 text-xs sm:text-sm rounded-2xl bg-[#0a0e17] border border-slate-700/80 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/80 focus:ring-1 focus:ring-indigo-500/40 shadow-xl resize-none overflow-y-auto"
            style={{ height: 'auto' }}
            onInput={(e) => {
              const t = e.target as HTMLTextAreaElement;
              t.style.height = 'auto';
              t.style.height = Math.min(t.scrollHeight, 120) + 'px';
            }}
          />
          <div className="absolute right-2 bottom-2 flex items-center gap-1.5">
            <Button
              type="submit"
              variant="glow"
              size="sm"
              disabled={!inputQuery.trim() || isTyping || isAnalyzing}
              rightIcon={<Send className="w-3.5 h-3.5" />}
              className="text-xs font-bold"
            >
              Ask
            </Button>
          </div>
        </form>
        <div className="flex items-center justify-between text-[11px] text-slate-500 text-center mt-2 px-1">
          <div className="flex items-center gap-1 text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>{isGeneralChat ? 'Clear, plain-language legal guidance' : 'Answers grounded in document vectors'}</span>
          </div>
          <span>LegalLens provides informational assistance and does not replace professional legal counsel.</span>
        </div>
      </div>

      {/* Source Citation Excerpt Modal */}
      {selectedSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg p-6 rounded-2xl bg-[#0d121d] border border-slate-700 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm">
                <FileText className="w-4 h-4" />
                <h4>Source Reference: {selectedSource.document_name ? `${selectedSource.document_name} • ` : ''}Page {selectedSource.page} • {selectedSource.section}</h4>
              </div>
              <button
                onClick={() => setSelectedSource(null)}
                className="text-slate-400 hover:text-white text-xs"
              >
                Close
              </button>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
              {selectedSource.quote ? `"${selectedSource.quote}"` : 'Direct clause verified by LegalLens RAG parser.'}
            </div>

            <div className="flex items-center justify-end pt-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setSelectedSource(null)}
                className="text-xs"
              >
                Done
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
