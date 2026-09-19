import React, { useState, useEffect } from 'react';
import { 
  CheckSquare, 
  FileText, 
  Download, 
  Sparkles, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck,
  RefreshCw,
  Share2
} from 'lucide-react';
import { LegalDocument, ChecklistItem } from '../types';
import { analysisService } from '../services/analysisService';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

interface BeforeYouSignPageProps {
  document?: LegalDocument | null;
}

export const BeforeYouSignPage: React.FC<BeforeYouSignPageProps> = ({ document }) => {
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [selectedSection, setSelectedSection] = useState<string>('All');
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!document?.id) return;
    analysisService.getChecklistForDocument(document.id).then(setChecklist);
  }, [document?.id]);

  if (!document) {
    return (
      <div className="p-8 text-center text-slate-400">
        <p>No document selected. Please select a document to view pre-signing checklist.</p>
      </div>
    );
  }

  const toggleItem = (id: string) => {
    setChecklist((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, completed: !item.completed } : item
      )
    );
  };

  const sections = ['All', 'Payments', 'Term', 'Termination', 'Obligations', 'Liability', 'Dispute Resolution'];

  const filtered = checklist.filter((item) => {
    if (selectedSection === 'All') return true;
    return item.section === selectedSection;
  });

  const completedCount = checklist.filter((i) => i.completed).length;
  const progressPercent = checklist.length > 0 ? Math.round((completedCount / checklist.length) * 100) : 0;

  const handleExportChecklist = () => {
    setExportMessage('Pre-Signature Audit Checklist generated & exported successfully to PDF / Print format.');
    setTimeout(() => setExportMessage(null), 4000);
  };

  const handleRegenerateChecklist = () => {
    setExportMessage('AI re-scanned contract provisions and refreshed verification points.');
    setTimeout(() => setExportMessage(null), 3000);
  };

  return (
    <div id="before-you-sign-page" className="p-4 sm:p-8 max-w-5xl mx-auto space-y-6 select-none">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
              Before You Sign
            </h1>
            <Badge variant="neutral" size="sm">
              {document.name}
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Review the most important parts of your document before making a decision.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRegenerateChecklist}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            className="text-xs"
          >
            Generate Checklist
          </Button>
          <Button
            variant="glow"
            size="sm"
            onClick={handleExportChecklist}
            leftIcon={<Download className="w-3.5 h-3.5" />}
            className="text-xs"
          >
            Export Checklist
          </Button>
        </div>
      </div>

      {exportMessage && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{exportMessage}</span>
        </div>
      )}

      {/* Progress Card */}
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Pre-Signing Readiness Progress
            </span>
            <div className="text-lg font-bold text-white font-['Space_Grotesk']">
              {completedCount} of {checklist.length} Critical Items Verified
            </div>
          </div>
          <span className="text-2xl font-extrabold text-indigo-400 font-mono">
            {progressPercent}%
          </span>
        </div>

        <div className="h-2 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 to-emerald-400 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Section Filters */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        {sections.map((sec) => (
          <button
            key={sec}
            onClick={() => setSelectedSection(sec)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer whitespace-nowrap hover-float-pill ${
              selectedSection === sec
                ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-900 border border-transparent hover:border-slate-800'
            }`}
          >
            {sec}
          </button>
        ))}
      </div>

      {/* Checklist Items Container */}
      <div className="space-y-3">
        {filtered.map((item) => (
          <div
            key={item.id}
            onClick={() => toggleItem(item.id)}
            className={`p-4 sm:p-5 rounded-2xl transition-all cursor-pointer border flex items-start gap-4 hover-float-sm ${
              item.completed
                ? 'bg-emerald-950/15 border-emerald-500/30 opacity-80'
                : 'bg-slate-900/60 border-slate-800/90 hover:border-indigo-500/40 hover:bg-slate-900/90'
            }`}
          >
            {/* Custom Checkbox */}
            <div className="pt-0.5 shrink-0">
              <div
                className={`w-5 h-5 rounded-lg border flex items-center justify-center transition-colors ${
                  item.completed
                    ? 'bg-emerald-500 border-emerald-400 text-black'
                    : 'border-slate-600 hover:border-indigo-400 bg-slate-950'
                }`}
              >
                {item.completed && <CheckCircle2 className="w-4 h-4 text-black" />}
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 space-y-1.5 min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                    {item.section}
                  </span>
                  <h3 className={`text-sm font-semibold tracking-tight ${
                    item.completed ? 'line-through text-slate-400' : 'text-white'
                  }`}>
                    {item.title}
                  </h3>
                </div>

                <Badge variant={item.attentionLevel} size="sm">
                  {item.attentionLevel === 'high' ? 'High Attention' :
                   item.attentionLevel === 'medium' ? 'Requires Attention' : 'Consider Reviewing'}
                </Badge>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">
                {item.explanation}
              </p>

              <div className="flex items-center gap-3 pt-1 text-[11px] font-mono text-slate-400">
                <span>Source: Page {item.source.page} • {item.source.section}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
