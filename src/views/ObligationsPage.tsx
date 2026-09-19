import React, { useState, useEffect } from 'react';
import { 
  Calendar, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  Filter, 
  Download, 
  FileText,
  User,
  Building,
  Check,
  ShieldAlert
} from 'lucide-react';
import { LegalDocument, ObligationItem } from '../types';
import { obligationService } from '../services/obligationService';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

interface ObligationsPageProps {
  document?: LegalDocument | null;
}

export const ObligationsPage: React.FC<ObligationsPageProps> = ({ document }) => {
  const [obligations, setObligations] = useState<ObligationItem[]>([]);
  const [filterMode, setFilterMode] = useState<'All' | 'My' | 'Other' | 'Critical'>('All');
  const [showCopiedToast, setShowCopiedToast] = useState(false);

  useEffect(() => {
    if (!document?.id) return;
    obligationService.getObligationsForDocument(document.id).then(setObligations);
  }, [document?.id]);

  if (!document) {
    return (
      <div className="p-8 text-center text-slate-400">
        <p>No document selected. Please select a document to view obligations.</p>
      </div>
    );
  }

  const filtered = obligations.filter((ob) => {
    if (filterMode === 'My') return ob.isMyObligation;
    if (filterMode === 'Other') return !ob.isMyObligation;
    if (filterMode === 'Critical') return ob.status === 'Critical' || ob.status === 'Upcoming';
    return true;
  });

  const handleExportCSV = () => {
    setShowCopiedToast(true);
    setTimeout(() => setShowCopiedToast(false), 3000);
  };

  return (
    <div id="obligations-page-view" className="p-4 sm:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
              Contract Obligations
            </h1>
            <Badge variant="neutral" size="sm">
              {document.name}
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Structured timeline of required actions, deadlines, and legal consequences.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCSV}
            leftIcon={<Download className="w-4 h-4" />}
            className="text-xs"
          >
            Export Obligations (.CSV)
          </Button>
        </div>
      </div>

      {showCopiedToast && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Obligations exported successfully to CSV summary.</span>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="p-2 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between gap-2 overflow-x-auto">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setFilterMode('All')}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer hover-float-pill ${
              filterMode === 'All'
                ? 'bg-indigo-600/25 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-850 hover:border hover:border-slate-800'
            }`}
          >
            All Obligations ({obligations.length})
          </button>
          <button
            onClick={() => setFilterMode('My')}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 hover-float-pill ${
              filterMode === 'My'
                ? 'bg-indigo-600/25 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-850 hover:border hover:border-slate-800'
            }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>My Obligations</span>
          </button>
          <button
            onClick={() => setFilterMode('Other')}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 hover-float-pill ${
              filterMode === 'Other'
                ? 'bg-indigo-600/25 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-850 hover:border hover:border-slate-800'
            }`}
          >
            <Building className="w-3.5 h-3.5" />
            <span>Other Party</span>
          </button>
          <button
            onClick={() => setFilterMode('Critical')}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 hover-float-pill ${
              filterMode === 'Critical'
                ? 'bg-amber-600/25 text-amber-300 border border-amber-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-850 hover:border hover:border-slate-800'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Upcoming Deadlines</span>
          </button>
        </div>

        <span className="text-xs text-slate-400 px-2 hidden sm:inline">
          Showing {filtered.length} of {obligations.length} records
        </span>
      </div>

      {/* Obligations Table */}
      <div className="rounded-2xl glass-panel border border-slate-800 overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/90 border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px] tracking-wider">
              <tr>
                <th className="py-3.5 px-4">Party</th>
                <th className="py-3.5 px-6">Obligation Description</th>
                <th className="py-3.5 px-4">Deadline / Frequency</th>
                <th className="py-3.5 px-6">Consequence of Non-Compliance</th>
                <th className="py-3.5 px-4">Source Clause</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((item) => (
                <tr key={item.id} className="hover:bg-slate-850/40 transition-colors">
                  {/* Party */}
                  <td className="py-4 px-4 whitespace-nowrap font-medium text-white">
                    <div className="flex items-center gap-2">
                      <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs ${
                        item.isMyObligation 
                          ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30' 
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}>
                        {item.isMyObligation ? <User className="w-3.5 h-3.5" /> : <Building className="w-3.5 h-3.5" />}
                      </div>
                      <span className={item.isMyObligation ? 'text-indigo-300 font-semibold' : 'text-slate-300'}>
                        {item.party}
                      </span>
                    </div>
                  </td>

                  {/* Obligation */}
                  <td className="py-4 px-6 text-slate-200 leading-relaxed font-sans max-w-sm">
                    {item.obligation}
                  </td>

                  {/* Deadline */}
                  <td className="py-4 px-4 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 font-mono text-[11px] font-semibold">
                      <Clock className="w-3 h-3 text-amber-400" />
                      {item.deadline}
                    </span>
                  </td>

                  {/* Consequence */}
                  <td className="py-4 px-6 text-slate-300 leading-relaxed max-w-xs">
                    <div className="flex items-start gap-1.5 text-xs text-rose-300/90">
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                      <span>{item.consequence}</span>
                    </div>
                  </td>

                  {/* Source */}
                  <td className="py-4 px-4 whitespace-nowrap font-mono text-[11px] text-slate-400">
                    <span className="p-1.5 rounded bg-slate-900 border border-slate-800">
                      p.{item.source.page} • {item.source.section}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
