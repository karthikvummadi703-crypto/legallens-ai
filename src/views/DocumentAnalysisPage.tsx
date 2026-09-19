import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Sparkles, 
  ShieldAlert, 
  AlertTriangle, 
  CheckCircle2, 
  CheckSquare,
  BookOpen, 
  MessageSquareText, 
  HelpCircle,
  Filter,
  Calendar,
  DollarSign,
  RefreshCw,
  Loader2,
  Brain,
  ShieldCheck,
  Info
} from 'lucide-react';
import { LegalDocument, LegalClause, RiskItem, FullAnalysisResponse, ExtractedPage } from '../types';
import { ScoreCard } from '../components/ui/ScoreCard';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ClauseCard } from '../components/cards/ClauseCard';
import { RiskCard } from '../components/cards/RiskCard';
import { analysisService } from '../services/analysisService';
import { documentService } from '../services/documentService';
import { NavView } from '../components/layout/Sidebar';

interface DocumentAnalysisPageProps {
  document?: LegalDocument | null;
  onNavigate: (view: NavView) => void;
}

type AnalysisTab = 'summary' | 'clauses' | 'risks' | 'obligations' | 'dates' | 'payments' | 'termination' | 'renewal' | 'lawyer';

export const DocumentAnalysisPage: React.FC<DocumentAnalysisPageProps> = ({
  document,
  onNavigate
}) => {
  const [activeTab, setActiveTab] = useState<AnalysisTab>('summary');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [clauses, setClauses] = useState<LegalClause[]>([]);
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [fullAnalysis, setFullAnalysis] = useState<FullAnalysisResponse | null>(null);
  const [documentDetails, setDocumentDetails] = useState<LegalDocument | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [loadingStep, setLoadingStep] = useState<string>('Preparing document');
  const [activeClauseId, setActiveClauseId] = useState<string>('');
  const [activePage, setActivePage] = useState<number>(1);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!document?.id) return;

    let isMounted = true;
    setErrorNotice(null);

    // Fetch full extracted document details (for real page text)
    documentService.getDocumentById(document.id).then((doc) => {
      if (isMounted && doc) {
        setDocumentDetails(doc);
      }
    });

    // Attempt loading existing analysis
    analysisService.getAnalysis(document.id).then((analysis) => {
      if (!isMounted) return;
      if (analysis) {
        setFullAnalysis(analysis);
      } else {
        // Run analysis pipeline if not yet analyzed
        runAnalysisPipeline(document.id);
      }
    });

    analysisService.getClausesForDocument(document.id).then((c) => isMounted && setClauses(c));
    analysisService.getRisksForDocument(document.id).then((r) => isMounted && setRisks(r));

    return () => {
      isMounted = false;
    };
  }, [document?.id]);

  const runAnalysisPipeline = async (docId: string) => {
    setIsAnalyzing(true);
    setErrorNotice(null);

    const steps = [
      'Preparing document context',
      'Analyzing clauses & structure',
      'Reviewing obligations & deadlines',
      'Identifying potential concerns',
      'Preparing AI insights'
    ];

    for (let i = 0; i < steps.length; i++) {
      setLoadingStep(steps[i]);
      await new Promise((r) => setTimeout(r, 400));
    }

    try {
      const result = await analysisService.analyzeDocument(docId);
      if (result) {
        setFullAnalysis(result);
        const fetchedClauses = await analysisService.getClausesForDocument(docId);
        const fetchedRisks = await analysisService.getRisksForDocument(docId);
        setClauses(fetchedClauses);
        setRisks(fetchedRisks);
      }
    } catch {
      setErrorNotice('Analysis could not complete at this time. Please retry to generate AI insights for this document.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (!document) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-4rem)] p-8 text-center text-slate-400">
        <FileText className="w-12 h-12 text-slate-600 mb-3" />
        <h2 className="text-lg font-bold text-white mb-1">No Document Selected</h2>
        <p className="text-sm max-w-sm mb-4">Please select a legal document from your repository or upload a new one to begin analysis.</p>
        <Button variant="glow" size="sm" onClick={() => onNavigate('documents')}>
          View All Documents
        </Button>
      </div>
    );
  }

  const activeDoc = documentDetails || document;
  const pagesCount = activeDoc.pageCount || (activeDoc.pages ? activeDoc.pages.length : 1);
  const displayScore = fullAnalysis?.attention_score?.score ?? activeDoc.attentionScore ?? 0;
  const scoreLabel = fullAnalysis?.attention_score?.label ?? (displayScore >= 80 ? 'Requires Immediate Attention' : displayScore >= 60 ? 'Requires Review' : 'Standard Terms');

  const categories = [
    'All',
    'Termination',
    'Payment',
    'Liability',
    'Renewal',
    'Confidentiality',
    'Dispute Resolution'
  ];

  const filteredClauses = clauses.filter((c) => {
    if (selectedCategory === 'All') return true;
    return c.category === selectedCategory || c.section.toLowerCase().includes(selectedCategory.toLowerCase());
  });

  const handleJumpToClause = (clauseRef: string) => {
    setActiveTab('clauses');
    const matched = clauses.find(c => c.clauseNumber.includes(clauseRef) || c.section.includes(clauseRef));
    if (matched) {
      setActiveClauseId(matched.id);
      setActivePage(matched.page);
    }
  };

  return (
    <div id="document-analysis-page" className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden bg-[#07090e]">
      {/* Top Document Header */}
      <div className="shrink-0 p-4 border-b border-slate-800/80 bg-[#0a0d15] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
            <FileText className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight truncate font-['Space_Grotesk']">
                {activeDoc.name}
              </h2>
              <Badge variant={isAnalyzing ? 'Processing' : (activeDoc.analysisStatus || 'Analyzed')} size="sm">
                {isAnalyzing ? 'Analyzing...' : (activeDoc.analysisStatus || 'Analyzed')}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
              <span>{activeDoc.type}</span>
              <span>•</span>
              <span>{pagesCount} Page{pagesCount > 1 ? 's' : ''}</span>
              <span>•</span>
              <span>Uploaded {activeDoc.uploadDate}</span>
            </div>
          </div>
        </div>

        {/* Score & Quick Actions */}
        <div className="flex items-center gap-3 shrink-0">
          <ScoreCard score={displayScore} label={scoreLabel} size="sm" />

          <Button
            variant="secondary"
            size="sm"
            onClick={() => runAnalysisPipeline(document.id)}
            disabled={isAnalyzing}
            leftIcon={isAnalyzing ? <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 text-indigo-400" />}
            className="text-xs"
          >
            {isAnalyzing ? 'Analyzing...' : 'Re-Analyze'}
          </Button>

          <Button
            variant="glow"
            size="sm"
            onClick={() => onNavigate('chat')}
            leftIcon={<MessageSquareText className="w-3.5 h-3.5 text-indigo-400" />}
            className="text-xs"
          >
            Ask AI
          </Button>
        </div>
      </div>

      {/* 3-COLUMN LAYOUT BODY */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* ======================================================== */}
        {/* COLUMN 1 (LEFT): Document Preview & Page Navigator (2 cols) */}
        {/* ======================================================== */}
        <div className="hidden xl:flex xl:col-span-2 flex-col border-r border-slate-800/80 bg-[#080b11] p-3.5 space-y-3 overflow-y-auto select-none">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider px-1">
            <span className="flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
              Page Navigator
            </span>
            <span className="text-[10px] font-mono text-slate-500">{pagesCount} Page{pagesCount > 1 ? 's' : ''}</span>
          </div>

          {/* Miniature Page Thumbnails */}
          <div className="space-y-2">
            {Array.from({ length: Math.max(1, pagesCount) }, (_, i) => i + 1).map((pg) => {
              const isSelected = activePage === pg;
              const hasHighAttention = risks.some(r => r.page === pg && r.attentionLevel === 'high');
              const hasMedAttention = risks.some(r => r.page === pg && r.attentionLevel === 'medium');
              const pageClauses = clauses.filter(c => c.page === pg).length;
              const pageRisks = risks.filter(r => r.page === pg).length;

              return (
                <div
                  key={pg}
                  onClick={() => setActivePage(pg)}
                  className={`p-2 rounded-xl transition-all cursor-pointer border flex items-center justify-between hover-float-sm ${
                    isSelected
                      ? 'bg-indigo-950/40 border-indigo-500/80 text-white shadow-sm'
                      : 'bg-slate-900/40 border-slate-800/60 text-slate-400 hover:border-indigo-500/40 hover:text-slate-200'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-6 h-8 rounded bg-slate-800/80 border border-slate-700/50 flex items-center justify-center text-[10px] font-mono font-bold text-slate-300 shrink-0">
                      {pg}
                    </div>
                    <div className="text-left min-w-0">
                      <p className="text-[10px] font-mono text-slate-500">Page {pg}</p>
                      {pageClauses > 0 || pageRisks > 0 ? (
                        <p className="text-[10px] text-slate-400 truncate">
                          {pageClauses} clause{pageClauses === 1 ? '' : 's'}{pageRisks > 0 ? ` • ${pageRisks} risk${pageRisks === 1 ? '' : 's'}` : ''}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  {hasHighAttention && (
                    <span className="w-2 h-2 rounded-full bg-rose-400 ring-2 ring-rose-400/20 shrink-0" title="High attention clause" />
                  )}
                  {hasMedAttention && !hasHighAttention && (
                    <span className="w-2 h-2 rounded-full bg-amber-400 ring-2 ring-amber-400/20 shrink-0" title="Review recommended" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ======================================================== */}
        {/* COLUMN 2 (CENTER): Extracted Page Text Canvas (5 cols)   */}
        {/* ======================================================== */}
        <div className="col-span-12 lg:col-span-6 xl:col-span-5 flex flex-col border-r border-slate-800/80 bg-[#0a0e17] overflow-hidden">
          {/* Sub-header */}
          <div className="p-3 border-b border-slate-800/80 bg-slate-900/60 flex items-center justify-between text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-300 uppercase tracking-wider text-[11px] font-mono">
                Document Text View
              </span>
              <span className="text-[11px] text-indigo-400 font-mono">
                Page {activePage} of {pagesCount}
              </span>
            </div>
            <span className="text-[11px] text-slate-500 hidden sm:inline">
              Page-aware extracted legal text
            </span>
          </div>

          {/* Formatted Contract Document Canvas */}
          <div className="flex-1 p-5 overflow-y-auto space-y-6 font-serif text-sm leading-relaxed text-slate-300">
            <div className="p-6 rounded-2xl bg-[#0e1320] border border-slate-800/90 shadow-xl space-y-6">
              <div className="text-center pb-4 border-b border-slate-800">
                <h3 className="text-base font-bold text-white uppercase tracking-wider font-mono">
                  {activeDoc.name.replace(/\.[^/.]+$/, '')}
                </h3>
                <p className="text-xs text-slate-400 mt-1 font-sans">
                  Grounded Page Extraction • Page {activePage}
                </p>
              </div>

              {/* Render dynamic extracted page text if available */}
              {activeDoc.pages && activeDoc.pages.length > 0 ? (
                <div className="space-y-4 font-sans text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                  <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-slate-300">
                    {activeDoc.pages.find(p => p.page_number === activePage)?.text || activeDoc.pages[0]?.text || 'Page text extracted by LegalLens pipeline.'}
                  </div>
                </div>
              ) : (
                /* No extracted text available yet */
                <div className="p-6 rounded-xl bg-slate-900/40 border border-slate-800 flex flex-col items-center text-center space-y-2">
                  <Info className="w-6 h-6 text-slate-500" />
                  <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                    Extracted page text is not available yet. Upload processing populates this view with the document's real text.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ======================================================== */}
        {/* COLUMN 3 (RIGHT): Gemini AI Document Intelligence Panel  */}
        {/* ======================================================== */}
        <div className="col-span-12 lg:col-span-6 xl:col-span-5 flex flex-col bg-[#07090e] overflow-hidden">
          {/* Analysis Header Tabs (All 9 Categories) */}
          <div className="p-3 border-b border-slate-800/80 bg-slate-900/60 overflow-x-auto select-none">
            <div className="flex items-center gap-1 min-w-max">
              <button
                onClick={() => setActiveTab('summary')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'summary' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Executive Summary
              </button>
              <button
                onClick={() => setActiveTab('clauses')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'clauses' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Clauses ({clauses.length})
              </button>
              <button
                onClick={() => setActiveTab('risks')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer flex items-center gap-1 ${
                  activeTab === 'risks' ? 'bg-rose-600/30 text-rose-300 border border-rose-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                <span>Risks</span>
                <span className="w-4 h-4 rounded-full bg-rose-500/30 text-rose-300 text-[10px] flex items-center justify-center font-mono">
                  {risks.length}
                </span>
              </button>
              <button
                onClick={() => setActiveTab('obligations')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'obligations' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Obligations ({fullAnalysis?.obligations?.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('dates')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'dates' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Dates
              </button>
              <button
                onClick={() => setActiveTab('payments')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'payments' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Payments
              </button>
              <button
                onClick={() => setActiveTab('termination')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'termination' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Termination
              </button>
              <button
                onClick={() => setActiveTab('renewal')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'renewal' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Renewal
              </button>
              <button
                onClick={() => setActiveTab('lawyer')}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'lawyer' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Lawyer Qs
              </button>
            </div>
          </div>

          {/* Loading State Overlay */}
          {isAnalyzing ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
              <div className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                <Brain className="w-8 h-8 text-indigo-400 animate-pulse" />
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-white">Gemini Legal Intelligence Pipeline</h4>
                <p className="text-xs text-indigo-300 font-mono animate-pulse">{loadingStep}...</p>
              </div>
            </div>
          ) : (
            /* Analysis Output Content */
            <div className="flex-1 p-4 sm:p-5 overflow-y-auto space-y-4">
              {errorNotice && (
                <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{errorNotice}</span>
                </div>
              )}

              {/* TAB 1: EXECUTIVE SUMMARY */}
              {activeTab === 'summary' && (
                <div className="space-y-4">
                  {fullAnalysis?.executive_summary ? (
                    <>
                      <div className="p-4 rounded-2xl bg-indigo-950/30 border border-indigo-500/30 space-y-3">
                        <div className="flex items-center gap-2 text-indigo-300 font-bold text-xs uppercase tracking-wider">
                          <Sparkles className="w-4 h-4 text-indigo-400" />
                          Executive Summary (Non-Lawyer Plain English)
                        </div>
                        <p className="text-xs text-slate-200 leading-relaxed font-sans">
                          {fullAnalysis.executive_summary.summary}
                        </p>
                      </div>

                      {fullAnalysis.executive_summary.key_points?.length > 0 && (
                        <div className="p-4 rounded-2xl glass-panel border border-slate-800 space-y-3">
                          <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                            Key Document Takeaways
                          </h4>
                          <ul className="space-y-2 text-xs text-slate-300">
                            {fullAnalysis.executive_summary.key_points.map((pt, idx) => (
                              <li key={idx} className="flex items-start gap-2">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                                <span>{pt}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-2">
                      <Sparkles className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No executive summary yet. Run the analysis pipeline to generate a plain-English summary of this document.
                      </p>
                    </div>
                  )}

                  {/* Attention Score Explanation Box */}
                  <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold text-white">
                      <span>Document Attention Score</span>
                      <span className="font-mono text-indigo-400">{displayScore}/100</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {fullAnalysis?.attention_score?.reasoning || 'Run the AI analysis pipeline to generate a transparent attention score breakdown for this document.'}
                    </p>
                    <p className="text-[10px] text-slate-500 pt-1 font-mono">
                      * Attention Score is an AI-generated document attention indicator, not a legal ruling.
                    </p>
                  </div>
                </div>
              )}

              {/* TAB 2: IMPORTANT CLAUSES */}
              {activeTab === 'clauses' && (
                <div className="space-y-4">
                  <div className="px-1 py-1 flex items-center gap-1.5 overflow-x-auto select-none">
                    {categories.map((cat) => (
                      <button
                        key={cat}
                        onClick={() => setSelectedCategory(cat)}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all whitespace-nowrap cursor-pointer ${
                          selectedCategory === cat ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>

                  {filteredClauses.length === 0 ? (
                    <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-2">
                      <FileText className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No clauses extracted yet. Run the analysis pipeline to identify important clauses in this document.
                      </p>
                    </div>
                  ) : (
                    filteredClauses.map((clause) => (
                      <ClauseCard
                        key={clause.id}
                        clause={clause}
                        isActive={activeClauseId === clause.id}
                        onSelect={(c) => {
                          setActiveClauseId(c.id);
                          setActivePage(c.page);
                        }}
                      />
                    ))
                  )}
                </div>
              )}

              {/* TAB 3: POTENTIAL RISKS */}
              {activeTab === 'risks' && (
                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-2.5 text-xs text-amber-300">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
                    <span>
                      AI flags potential concerns using guarded language for your awareness. Consider reviewing these provisions prior to signing.
                    </span>
                  </div>

                  {risks.length === 0 ? (
                    <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-2">
                      <ShieldAlert className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No risks identified yet. Run the analysis pipeline to detect potential concerns in this document.
                      </p>
                    </div>
                  ) : (
                    risks.map((risk) => (
                      <RiskCard
                        key={risk.id}
                        risk={risk}
                        onViewClause={(ref) => handleJumpToClause(ref)}
                      />
                    ))
                  )}
                </div>
              )}

              {/* TAB 4: OBLIGATIONS */}
              {activeTab === 'obligations' && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                    Extracted Contractual Obligations
                  </h4>
                  {fullAnalysis?.obligations && fullAnalysis.obligations.length > 0 ? (
                    fullAnalysis.obligations.map((ob, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl glass-panel border border-slate-800 space-y-1.5 text-xs">
                        <div className="flex items-center justify-between text-indigo-300 font-semibold">
                          <span>Party: {ob.party}</span>
                          <span className="text-[10px] text-slate-500 font-mono">Page {ob.page} • {ob.section}</span>
                        </div>
                        <p className="text-white font-medium">{ob.obligation}</p>
                        <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/60">
                          <span>Deadline: <span className="text-slate-200">{ob.deadline}</span></span>
                          <span>Consequence: <span className="text-rose-300">{ob.consequence}</span></span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-2">
                      <CheckSquare className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No obligations extracted yet. Run the analysis pipeline to surface duties and deadlines in this document.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 5: KEY DATES */}
              {activeTab === 'dates' && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                    Important Dates & Timeframes
                  </h4>
                  {fullAnalysis?.key_dates && fullAnalysis.key_dates.length > 0 ? (
                    fullAnalysis.key_dates.map((kd, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl glass-panel border border-slate-800 flex items-center justify-between text-xs">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                            <span className="font-semibold text-white">{kd.event}</span>
                          </div>
                          <p className="text-slate-300 font-mono text-[11px] pl-5.5">{kd.date_or_period}</p>
                        </div>
                        <span className="text-[10px] font-mono text-slate-500">Page {kd.page}</span>
                      </div>
                    ))
                  ) : (
                    <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-2">
                      <Calendar className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No key dates identified yet. Run the analysis pipeline to surface deadlines and important dates.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 6: PAYMENTS */}
              {activeTab === 'payments' && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                    Payments & Financial Considerations
                  </h4>
                  {fullAnalysis?.payments && fullAnalysis.payments.length > 0 ? (
                    fullAnalysis.payments.map((p, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl glass-panel border border-slate-800 space-y-1.5 text-xs">
                        <div className="flex items-center justify-between font-semibold">
                          <span className="text-white">{p.item}</span>
                          <span className="text-emerald-400 font-mono font-bold">{p.amount}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 pt-1">
                          <div>Frequency: <span className="text-slate-200">{p.frequency}</span></div>
                          <div>Due Date: <span className="text-slate-200">{p.due_date}</span></div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-2">
                      <DollarSign className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No payment terms identified yet. Run the analysis pipeline to surface financial obligations in this document.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 7: TERMINATION */}
              {activeTab === 'termination' && (
                <div className="p-4 rounded-2xl glass-panel border border-slate-800 space-y-3 text-xs">
                  <h4 className="font-bold text-white uppercase tracking-wider font-mono">
                    Termination Conditions Analysis
                  </h4>
                  {fullAnalysis?.termination_analysis ? (
                    <>
                      <p className="text-slate-300 leading-relaxed">
                        {fullAnalysis.termination_analysis.summary}
                      </p>
                      <div className="space-y-2 pt-2 border-t border-slate-800/60 text-slate-400">
                        <div>Who Can Terminate: <span className="text-slate-200">{fullAnalysis.termination_analysis.who_can_terminate}</span></div>
                        <div>Notice Period: <span className="text-slate-200">{fullAnalysis.termination_analysis.notice_period}</span></div>
                        <div>Penalties: <span className="text-rose-300">{fullAnalysis.termination_analysis.penalties}</span></div>
                        <div>Cure Period: <span className="text-slate-200">{fullAnalysis.termination_analysis.cure_period}</span></div>
                      </div>
                    </>
                  ) : (
                    <div className="py-4 flex flex-col items-center text-center space-y-2">
                      <AlertTriangle className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No termination analysis yet. Run the analysis pipeline to review how this document can be terminated.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 8: RENEWAL */}
              {activeTab === 'renewal' && (
                <div className="p-4 rounded-2xl glass-panel border border-slate-800 space-y-3 text-xs">
                  <h4 className="font-bold text-white uppercase tracking-wider font-mono">
                    Renewal & Extension Analysis
                  </h4>
                  {fullAnalysis?.renewal_analysis ? (
                    <>
                      <p className="text-slate-300 leading-relaxed">
                        {fullAnalysis.renewal_analysis.summary}
                      </p>
                      <div className="space-y-2 pt-2 border-t border-slate-800/60 text-slate-400">
                        <div>Automatic Renewal: <span className="text-indigo-300 font-semibold">{fullAnalysis.renewal_analysis.automatic_renewal ? 'Yes' : 'No'}</span></div>
                        <div>Notice Required for Non-Renewal: <span className="text-slate-200">{fullAnalysis.renewal_analysis.notice_period}</span></div>
                        <div>Opt-Out Method: <span className="text-slate-200">{fullAnalysis.renewal_analysis.opt_out}</span></div>
                      </div>
                    </>
                  ) : (
                    <div className="py-4 flex flex-col items-center text-center space-y-2">
                      <RefreshCw className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No renewal analysis yet. Run the analysis pipeline to review automatic renewal and opt-out terms.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 9: LAWYER QUESTIONS */}
              {activeTab === 'lawyer' && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                    Recommended Questions for a Lawyer
                  </h4>
                  {fullAnalysis?.lawyer_questions && fullAnalysis.lawyer_questions.length > 0 ? (
                    fullAnalysis.lawyer_questions.map((q, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl glass-panel border border-slate-800 space-y-1 text-xs">
                        <p className="font-semibold text-indigo-300">"{q.question}"</p>
                        <p className="text-slate-400 text-[11px]">Context: {q.context}</p>
                        <p className="text-[10px] text-slate-500 font-mono pt-1">Source: Page {q.page} • {q.section}</p>
                      </div>
                    ))
                  ) : (
                    <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-2">
                      <HelpCircle className="w-6 h-6 text-slate-500" />
                      <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                        No lawyer questions generated yet. Run the analysis pipeline to surface questions worth raising with counsel.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* MANDATORY PRODUCT DISCLAIMER FOOTER */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-400 flex items-center gap-2 mt-4">
                <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                <span>
                  {fullAnalysis?.disclaimer || 'LegalLens provides informational assistance and does not replace professional legal advice.'}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
