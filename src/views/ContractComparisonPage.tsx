import React, { useState, useEffect } from 'react';
import { 
  GitCompare, 
  FileText, 
  Sparkles, 
  ArrowRight, 
  PlusCircle, 
  MinusCircle, 
  RefreshCw, 
  CheckCircle2, 
  AlertTriangle,
  Lightbulb,
  ShieldCheck,
  ChevronRight
} from 'lucide-react';
import { DocumentComparison, LegalDocument } from '../types';
import { comparisonService } from '../services/comparisonService';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

interface ContractComparisonPageProps {
  documents: LegalDocument[];
  onOpenUpload: () => void;
}

export const ContractComparisonPage: React.FC<ContractComparisonPageProps> = ({
  documents,
  onOpenUpload
}) => {
  const [comparison, setComparison] = useState<DocumentComparison | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string>('All');
  const [selectedDiffId, setSelectedDiffId] = useState<string>('diff-1');

  useEffect(() => {
    comparisonService.compareDocuments('doc-saas-03', 'doc-saas-revised').then((result) => {
      if (result) {
        setComparison(result);
      } else {
        setLoadError('Contract comparison is not available yet. This feature requires two documents to be selected for side-by-side analysis.');
      }
    });
  }, []);

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-4rem)] p-8 text-center text-slate-400">
        <GitCompare className="w-12 h-12 text-slate-600 mb-3" />
        <h2 className="text-lg font-bold text-white mb-1">Comparison Unavailable</h2>
        <p className="text-sm max-w-sm mb-4">{loadError}</p>
        <Button variant="glow" size="sm" onClick={onOpenUpload}>
          Upload Documents
        </Button>
      </div>
    );
  }

  if (!comparison) {
    return (
      <div className="p-8 text-center text-slate-400">
        Loading comparison intelligence...
      </div>
    );
  }

  const filteredDiffs = comparison.differences.filter((diff) => {
    if (selectedFilter === 'All') return true;
    return diff.differenceType === selectedFilter;
  });

  const activeDiff = comparison.differences.find(d => d.id === selectedDiffId) || comparison.differences[0];

  return (
    <div id="contract-comparison-page" className="p-4 sm:p-8 max-w-7xl mx-auto space-y-6 select-none">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
            Compare Contracts
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Detect additions, deletions, modified liability caps, and changed payment terms.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={onOpenUpload}
          leftIcon={<GitCompare className="w-4 h-4" />}
          className="text-xs"
        >
          Compare Different File
        </Button>
      </div>

      {/* Visual Contract Selectors: Document A vs Document B */}
      <div className="grid grid-cols-1 md:grid-cols-11 gap-4 items-center">
        {/* Document A Card */}
        <div className="md:col-span-5 p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-mono text-indigo-400 font-bold uppercase">Contract A (Original)</span>
            <span>Version 1.2</span>
          </div>
          <div className="flex items-center gap-2.5">
            <FileText className="w-5 h-5 text-indigo-400 shrink-0" />
            <span className="text-sm font-semibold text-white truncate">
              {comparison.documentAName}
            </span>
          </div>
        </div>

        {/* Center Divider Icon */}
        <div className="md:col-span-1 flex justify-center">
          <div className="w-10 h-10 rounded-full bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 flex items-center justify-center font-bold text-xs">
            VS
          </div>
        </div>

        {/* Document B Card */}
        <div className="md:col-span-5 p-4 rounded-2xl bg-indigo-950/30 border border-indigo-500/40 space-y-2">
          <div className="flex items-center justify-between text-xs text-indigo-300">
            <span className="font-mono text-emerald-400 font-bold uppercase">Contract B (Revised)</span>
            <span className="bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded text-[10px]">Newest</span>
          </div>
          <div className="flex items-center gap-2.5">
            <FileText className="w-5 h-5 text-emerald-400 shrink-0" />
            <span className="text-sm font-semibold text-white truncate">
              {comparison.documentBName}
            </span>
          </div>
        </div>
      </div>

      {/* Visual Summary Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="text-xs text-slate-400">Total Changes</div>
          <div className="text-2xl font-extrabold text-white font-['Space_Grotesk']">
            {comparison.summary.totalChanged} clauses changed
          </div>
        </div>

        <div className="p-4 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="text-xs text-slate-400">Obligation Impact</div>
          <div className="text-2xl font-extrabold text-indigo-300 font-['Space_Grotesk']">
            +{comparison.summary.newObligations} new obligations
          </div>
        </div>

        <div className="p-4 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="text-xs text-slate-400">Financial Impact</div>
          <div className="text-2xl font-extrabold text-amber-300 font-['Space_Grotesk']">
            {comparison.summary.paymentChanges} payment change
          </div>
        </div>

        <div className="p-4 rounded-2xl glass-panel border border-slate-800 space-y-1 hover-float cursor-default">
          <div className="text-xs text-slate-400">Language Refinements</div>
          <div className="text-2xl font-extrabold text-sky-300 font-['Space_Grotesk']">
            {comparison.summary.wordingChanges} wording changes
          </div>
        </div>
      </div>

      {/* "Why does this matter?" AI Explanation Featured Banner */}
      {activeDiff && (
        <div className="p-5 rounded-2xl bg-indigo-950/40 border border-indigo-500/40 space-y-2 relative overflow-hidden hover-float-sm">
          <div className="flex items-center gap-2 text-indigo-300">
            <Lightbulb className="w-4 h-4 text-amber-400 shrink-0" />
            <h3 className="text-sm font-bold tracking-tight">
              Why does this matter? — {activeDiff.clauseTitle}
            </h3>
          </div>
          <p className="text-xs text-slate-200 leading-relaxed font-sans">
            {activeDiff.aiExplanation}
          </p>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {['All', 'Changed', 'Added', 'Removed'].map((filter) => (
          <button
            key={filter}
            onClick={() => setSelectedFilter(filter)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer hover-float-pill ${
              selectedFilter === filter
                ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/50 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-900 border border-transparent hover:border-slate-800'
            }`}
          >
            {filter} ({filter === 'All' ? comparison.differences.length : comparison.differences.filter(d => d.differenceType === filter).length})
          </button>
        ))}
      </div>

      {/* Side-by-Side Comparison Table */}
      <div className="rounded-2xl glass-panel border border-slate-800 overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/90 border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px] tracking-wider">
              <tr>
                <th className="py-3.5 px-4 w-1/5">Clause & Topic</th>
                <th className="py-3.5 px-4 w-1/3">Contract A (Original)</th>
                <th className="py-3.5 px-4 w-1/3">Contract B (Revised Proposal)</th>
                <th className="py-3.5 px-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredDiffs.map((diff) => {
                const isSelected = activeDiff?.id === diff.id;
                return (
                  <tr
                    key={diff.id}
                    onClick={() => setSelectedDiffId(diff.id)}
                    className={`transition-colors cursor-pointer ${
                      isSelected ? 'bg-indigo-950/30' : 'hover:bg-slate-850/40'
                    }`}
                  >
                    {/* Clause Name */}
                    <td className="py-4 px-4 font-semibold text-white align-top">
                      <div className="space-y-1">
                        <span className="font-['Space_Grotesk'] text-sm">{diff.clauseTitle}</span>
                        <span className="block text-[10px] font-mono text-indigo-400">
                          {diff.category}
                        </span>
                      </div>
                    </td>

                    {/* Contract A text */}
                    <td className="py-4 px-4 text-slate-300 font-sans leading-relaxed align-top">
                      <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                        {diff.contractA}
                      </div>
                    </td>

                    {/* Contract B text */}
                    <td className="py-4 px-4 text-slate-200 font-sans leading-relaxed align-top">
                      <div className={`p-2.5 rounded-lg border ${
                        diff.differenceType === 'Added' ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-200' :
                        diff.differenceType === 'Removed' ? 'bg-rose-950/20 border-rose-500/30 text-rose-300 line-through' :
                        'bg-indigo-950/20 border-indigo-500/30 text-slate-100'
                      }`}>
                        {diff.contractB}
                      </div>
                    </td>

                    {/* Difference type badge */}
                    <td className="py-4 px-4 text-center align-top whitespace-nowrap">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold font-mono ${
                        diff.differenceType === 'Added' ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30' :
                        diff.differenceType === 'Removed' ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30' :
                        'bg-sky-500/15 text-sky-300 border border-sky-500/30'
                      }`}>
                        {diff.differenceType}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
