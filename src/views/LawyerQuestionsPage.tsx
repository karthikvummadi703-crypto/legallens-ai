import React, { useState } from 'react';
import { 
  HelpCircle, 
  Copy, 
  Check, 
  Download, 
  FileText, 
  Bookmark, 
  BookmarkCheck, 
  CheckCircle2, 
  Sparkles,
  ExternalLink
} from 'lucide-react';
import { LegalDocument } from '../types';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

interface LawyerQuestionsPageProps {
  document?: LegalDocument | null;
}

interface LawyerQuestionItem {
  id: string;
  category: string;
  question: string;
  sourceClause: string;
  whyItMatters: string;
  isSaved?: boolean;
  isDiscussed?: boolean;
}

export const LawyerQuestionsPage: React.FC<LawyerQuestionsPageProps> = ({ document }) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  if (!document) {
    return (
      <div className="p-8 text-center text-slate-400">
        <p>No document selected. Please select a document to generate questions for your lawyer.</p>
      </div>
    );
  }

  const [questions, setQuestions] = useState<LawyerQuestionItem[]>([
    {
      id: 'q-1',
      category: 'Termination & Repayment',
      question: 'Is the clause requiring 100% repayment of relocation assistance and 50% signing bonus upon voluntary departure within 12 months standard or legally enforceable in Delaware without proration?',
      sourceClause: 'Section 8.1 • Page 6',
      whyItMatters: 'If you leave due to unforeseen circumstances, the company can unilaterally withhold or demand $45,000 immediately.',
      isSaved: true,
      isDiscussed: false
    },
    {
      id: 'q-2',
      category: 'Compensation & Clawbacks',
      question: 'Can the 18-month bonus clawback be narrowed to require formal arbitration findings of fraud or intentional malfeasance, rather than sole board discretion?',
      sourceClause: 'Section 3.3 • Page 3',
      whyItMatters: 'Vague terms like "reputational harm" give executive boards excessive discretion to retract previously earned bonuses.',
      isSaved: false,
      isDiscussed: false
    },
    {
      id: 'q-3',
      category: 'Restrictive Covenants',
      question: 'Does the 12-month post-employment non-compete include reasonable geographic and functional carve-outs for non-competitive AI engineering consulting?',
      sourceClause: 'Section 6.1 • Page 5',
      whyItMatters: 'A broad prohibition on "AI document analysis technology" across North America and EU could severely hinder subsequent career opportunities.',
      isSaved: true,
      isDiscussed: true
    },
    {
      id: 'q-4',
      category: 'Notice & Administrative Leave',
      question: 'Can we amend Section 8.2 so that if the company places me on administrative leave during the 60-day notice window, my salary and benefits remain fully paid?',
      sourceClause: 'Section 8.2 • Page 6',
      whyItMatters: 'Unpaid administrative leave during mandatory notice is functionally equivalent to an unpaid suspension.',
      isSaved: false,
      isDiscussed: false
    },
    {
      id: 'q-5',
      category: 'Dispute Resolution',
      question: 'Should we insist on a mutual loser-pays attorney fee provision or carve out preliminary injunctive relief for intellectual property?',
      sourceClause: 'Section 10.2 • Page 9',
      whyItMatters: 'Mandatory private arbitration in Delaware imposes substantial administrative costs that can discourage valid claims.',
      isSaved: false,
      isDiscussed: false
    }
  ]);

  const categories = ['All', 'Termination & Repayment', 'Compensation & Clawbacks', 'Restrictive Covenants', 'Notice & Administrative Leave', 'Dispute Resolution'];

  const filtered = questions.filter(q => selectedCategory === 'All' || q.category === selectedCategory);

  const toggleSave = (id: string) => {
    setQuestions(prev => prev.map(q => q.id === id ? { ...q, isSaved: !q.isSaved } : q));
  };

  const toggleDiscussed = (id: string) => {
    setQuestions(prev => prev.map(q => q.id === id ? { ...q, isDiscussed: !q.isDiscussed } : q));
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportBrief = () => {
    setExportNotice('Consultation Brief generated and formatted for your attorney meeting.');
    setTimeout(() => setExportNotice(null), 3500);
  };

  return (
    <div id="lawyer-questions-page" className="p-4 sm:p-8 max-w-5xl mx-auto space-y-6 select-none">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
              Questions for Your Lawyer
            </h1>
            <Badge variant="neutral" size="sm">
              {document.name}
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Generated questions to help you consult legal counsel effectively.
          </p>
        </div>

        <Button
          variant="glow"
          size="sm"
          onClick={handleExportBrief}
          leftIcon={<Download className="w-4 h-4" />}
          className="text-xs"
        >
          Export Consultation Brief
        </Button>
      </div>

      {exportNotice && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{exportNotice}</span>
        </div>
      )}

      {/* Category Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all whitespace-nowrap cursor-pointer hover-float-pill ${
              selectedCategory === cat
                ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-900 border border-transparent hover:border-slate-800'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Questions list */}
      <div className="space-y-4">
        {filtered.map(item => (
          <div
            key={item.id}
            className={`p-5 rounded-2xl glass-panel border transition-all space-y-3 hover-float-sm ${
              item.isDiscussed 
                ? 'border-emerald-500/30 bg-emerald-950/10' 
                : 'border-slate-800 hover:border-indigo-500/40'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-indigo-400 uppercase px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">
                    {item.category}
                  </span>
                  <span className="text-xs text-slate-500 font-mono">
                    Ref: {item.sourceClause}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-white leading-relaxed pt-1">
                  "{item.question}"
                </h3>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={() => handleCopy(item.id, item.question)}
                  className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  title="Copy question text"
                >
                  {copiedId === item.id ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </button>

                <button
                  onClick={() => toggleSave(item.id)}
                  className={`p-2 rounded-xl transition-colors ${
                    item.isSaved ? 'text-indigo-400 bg-indigo-500/15' : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }`}
                  title={item.isSaved ? 'Saved to briefing' : 'Save for meeting'}
                >
                  {item.isSaved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                </button>

                <button
                  onClick={() => toggleDiscussed(item.id)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs font-medium transition-colors ${
                    item.isDiscussed 
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
                      : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {item.isDiscussed ? 'Discussed ✓' : 'Mark Discussed'}
                </button>
              </div>
            </div>

            {/* Why this matters container */}
            <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 text-xs text-slate-300 space-y-1">
              <span className="text-[10px] font-mono uppercase font-bold text-amber-400 tracking-wider">
                Why this matters to you:
              </span>
              <p className="text-slate-300 leading-relaxed font-sans">
                {item.whyItMatters}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
