import React from 'react';
import {
  UploadCloud,
  SearchCode,
  GitCompare,
  MessageSquareText,
  CheckSquare,
  FileText,
  ShieldAlert,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  Layers,
  HelpCircle,
  Inbox
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { ScoreCard } from '../components/ui/ScoreCard';
import { TrustBanner } from '../components/common/TrustBanner';
import { DocumentCard } from '../components/cards/DocumentCard';
import { 
  LegalDocument, 
  UserProfile, 
} from '../types';
import { NavView } from '../components/layout/Sidebar';
import { AeroShards } from '../components/ui/AeroShards';

interface HomeDashboardProps {
  user: UserProfile;
  documents: LegalDocument[];
  onSelectDocument: (doc: LegalDocument) => void;
  onNavigate: (view: NavView) => void;
  onOpenUpload: () => void;
}

export const HomeDashboard: React.FC<HomeDashboardProps> = ({
  user,
  documents,
  onSelectDocument,
  onNavigate,
  onOpenUpload
}) => {
  const docsAnalyzed = documents.filter(d => d.analysisStatus !== 'Processing');
  const totalRisks = documents.reduce((sum, d) => sum + (d.risksCount || 0), 0);
  const totalClauses = documents.reduce((sum, d) => sum + (d.clausesCount || 0), 0);
  const totalObligations = documents.reduce((sum, d) => sum + (d.obligationsCount || 0), 0);
  const avgScore = docsAnalyzed.length > 0
    ? Math.round(docsAnalyzed.reduce((sum, d) => sum + (d.attentionScore || 0), 0) / docsAnalyzed.length)
    : 0;

  const highAttentionDocs = documents.filter(d => (d.attentionScore || 0) >= 70 && d.analysisStatus !== 'Processing');

  const quickActions = [
    {
      id: 'qa-upload',
      title: 'Upload Document',
      desc: 'Drag & drop contracts or PDF agreements for rapid AI synthesis.',
      icon: UploadCloud,
      action: onOpenUpload,
      accent: 'from-blue-500/10 to-indigo-500/10 border-indigo-500/30 text-indigo-400'
    },
    {
      id: 'qa-analyze',
      title: 'Analyze Document',
      desc: 'Inspect deep 3-column clause breakdown, scores, and risks.',
      icon: SearchCode,
      action: () => onNavigate('analyze'),
      accent: 'from-purple-500/10 to-violet-500/10 border-violet-500/30 text-violet-400'
    },
    {
      id: 'qa-compare',
      title: 'Compare Contracts',
      desc: 'Highlight newly added, removed, or changed clauses side-by-side.',
      icon: GitCompare,
      action: () => onNavigate('compare'),
      accent: 'from-emerald-500/10 to-teal-500/10 border-teal-500/30 text-teal-400'
    },
    {
      id: 'qa-chat',
      title: 'Ask LegalLens',
      desc: 'Chat with your document with clickable grounded source citations.',
      icon: MessageSquareText,
      action: () => onNavigate('chat'),
      accent: 'from-sky-500/10 to-cyan-500/10 border-sky-500/30 text-sky-400'
    },
    {
      id: 'qa-checklist',
      title: 'Before You Sign',
      desc: 'Interactive checklist verifying payments, liabilities, and notice terms.',
      icon: CheckSquare,
      action: () => onNavigate('checklist'),
      accent: 'from-amber-500/10 to-orange-500/10 border-amber-500/30 text-amber-400'
    },
  ];

  return (
    <div id="home-dashboard-view" className="relative space-y-8 p-4 sm:p-8 max-w-7xl mx-auto">
      {/* Background Animated AeroShards */}
      <div className="fixed inset-0 pointer-events-none z-0 opacity-20 overflow-hidden">
        <AeroShards
          backgroundColor="#07090e"
          shardColor="#4f46e5"
          accentColor="#8b5cf6"
          placement="full"
          flow="ribbon"
          material="pearl"
          detail="balanced"
          scale={1.35}
          spread={1.05}
          depth={0.8}
          speed={0.4}
          spin={0.8}
          interaction="repel"
          density={1.2}
          shardSize={1.0}
          glow={1.4}
          bloom={0.8}
          grain={0.04}
          chromaticAberration={0.005}
          holdToGather={true}
        />
      </div>

      {/* Top Greeting Header */}
      <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
            Good morning, {user?.name ? user.name.split(' ')[0] : 'there'}
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Here's an overview of your legal workspace.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <TrustBanner variant="compact" />
        </div>
      </div>

      {/* Hero Card: "Your legal documents, made understandable." */}
      <div className="relative z-10 rounded-3xl p-6 sm:p-8 glass-panel border border-indigo-500/30 overflow-hidden shadow-xl shadow-black/40">
        {/* Animated AeroShards Stream on the right */}
        <div className="absolute inset-0 z-0 pointer-events-auto opacity-75">
          <AeroShards
            backgroundColor="#0a0d18"
            shardColor="#4338ca"
            accentColor="#38bdf8"
            placement="right"
            flow="stream"
            material="chrome"
            detail="balanced"
            scale={1.3}
            spread={0.9}
            depth={0.7}
            speed={0.5}
            spin={1.0}
            interaction="attract"
            density={1.3}
            shardSize={1.1}
            glow={1.6}
            bloom={1.0}
            grain={0.05}
            chromaticAberration={0.006}
            holdToGather={true}
          />
        </div>

        {/* Ambient Gradient Glow */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-80 h-80 bg-indigo-500/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 -mb-10 w-60 h-60 bg-violet-500/15 rounded-full blur-2xl pointer-events-none" />

        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Workspace Intelligence Ready</span>
          </div>

          <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight font-['Space_Grotesk'] leading-tight">
            Your legal documents, <br className="hidden sm:inline" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 via-sky-200 to-violet-300">
              made understandable.
            </span>
          </h2>

          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed max-w-xl">
            Upload a document to uncover important clauses, potential risks, obligations, and answers.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <Button
              variant="glow"
              size="md"
              onClick={onOpenUpload}
              leftIcon={<UploadCloud className="w-4 h-4" />}
            >
              Upload Document
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => onNavigate('documents')}
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              View Documents
            </Button>
          </div>
        </div>
      </div>

      {/* Analytics Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Documents Analyzed</span>
            <FileText className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-extrabold text-white font-['Space_Grotesk'] tracking-tight">
            {documents.length}
          </div>
          <p className="text-[11px] text-slate-400">Total contracts uploaded</p>
        </div>

        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Potential Risks</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-3xl font-extrabold text-rose-300 font-['Space_Grotesk'] tracking-tight">
            {totalRisks}
          </div>
          <p className="text-[11px] text-rose-400/80">Require closer attention</p>
        </div>

        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Important Clauses</span>
            <Layers className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-extrabold text-amber-300 font-['Space_Grotesk'] tracking-tight">
            {totalClauses}
          </div>
          <p className="text-[11px] text-amber-400/80">Extracted & summarized</p>
        </div>

        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Obligations Tracked</span>
            <HelpCircle className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-3xl font-extrabold text-sky-300 font-['Space_Grotesk'] tracking-tight">
            {totalObligations}
          </div>
          <p className="text-[11px] text-sky-400/80">Across all documents</p>
        </div>
      </div>

      {/* Quick Actions Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-white tracking-tight font-['Space_Grotesk']">
            Quick Actions
          </h3>
          <span className="text-xs text-slate-400">Select an intelligence task</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
          {quickActions.map((qa) => {
            const Icon = qa.icon;
            return (
              <div
                key={qa.id}
                onClick={qa.action}
                className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-indigo-500/50 hover:bg-slate-850 cursor-pointer group flex flex-col justify-between gap-3 select-none hover-float"
              >
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center border bg-gradient-to-br ${qa.accent}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-white tracking-tight group-hover:text-indigo-300 transition-colors">
                    {qa.title}
                  </h4>
                  <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                    {qa.desc}
                  </p>
                </div>
                <div className="flex items-center text-[10px] font-semibold text-indigo-400 group-hover:translate-x-0.5 transition-transform">
                  <span>Launch</span>
                  <ArrowRight className="w-3 h-3 ml-1" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Documents Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-white tracking-tight font-['Space_Grotesk']">
              Recent Documents
            </h3>
            <p className="text-xs text-slate-400">Review status and attention scores</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigate('documents')}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            className="text-xs"
          >
            View All Documents
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {documents.slice(0, 4).map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              onSelect={() => {
                onSelectDocument(doc);
                onNavigate('analyze');
              }}
              onAnalyze={() => {
                onSelectDocument(doc);
                onNavigate('analyze');
              }}
            />
          ))}
        </div>
      </div>

      {/* Insights Section */}
      {documents.length === 0 ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-white tracking-tight font-['Space_Grotesk']">
                Workspace Insights
              </h3>
              <p className="text-xs text-slate-400">Begin analyzing documents to see insights here</p>
            </div>
          </div>

          <div className="p-8 rounded-3xl glass-panel border border-slate-800 flex flex-col items-center text-center space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Inbox className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-white">No documents uploaded yet</h4>
            <p className="text-xs text-slate-400 max-w-md leading-relaxed">
              Upload your first contract to unlock AI clause extraction, risk flags, obligations, and grounded chat analysis.
            </p>
            <Button
              variant="glow"
              size="sm"
              onClick={onOpenUpload}
              leftIcon={<UploadCloud className="w-4 h-4" />}
              className="mt-2"
            >
              Upload Your First Document
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-white tracking-tight font-['Space_Grotesk']">
                Attention Overview
              </h3>
              <p className="text-xs text-slate-400">Documents flagged for closer review</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate('analyze')}
              className="text-xs"
            >
              Open Full Analysis
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* High Attention Documents */}
            <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-rose-400" />
                  <h4 className="text-sm font-semibold text-white">High Attention Documents</h4>
                </div>
                <span className="text-xs text-slate-400 font-mono">{highAttentionDocs.length}</span>
              </div>

              {highAttentionDocs.length === 0 ? (
                <p className="text-xs text-slate-400 leading-relaxed">
                  No documents above the 70 attention threshold. Your analyzed documents are tracking normally so far.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {highAttentionDocs.slice(0, 3).map((doc) => (
                    <div
                      key={doc.id}
                      onClick={() => {
                        onSelectDocument(doc);
                        onNavigate('analyze');
                      }}
                      className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-indigo-500/40 transition-all cursor-pointer space-y-1.5 hover-float-sm"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-rose-300 truncate pr-2">{doc.name}</span>
                        <span className="text-[10px] text-slate-400 font-mono shrink-0">{doc.attentionScore}/100</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed line-clamp-2">
                        {doc.summary || 'Document uploaded to your workspace.'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Average Attention Score */}
            <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <h4 className="text-sm font-semibold text-white">Overall Attention Score</h4>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <ScoreCard score={avgScore} label={avgScore >= 70 ? 'Requires Review' : avgScore >= 40 ? 'Monitor Regularly' : 'Standard Terms'} size="md" />
                <p className="text-xs text-slate-400 leading-relaxed">
                  Average attention indicator across {docsAnalyzed.length} analyzed document{docsAnalyzed.length === 1 ? '' : 's'}. Higher scores signal clauses worth reviewing before signing.
                </p>
              </div>

              {totalObligations > 0 && (
                <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs">
                  <span className="text-slate-400">Active obligations tracked</span>
                  <span className="text-indigo-300 font-semibold font-mono">{totalObligations}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
