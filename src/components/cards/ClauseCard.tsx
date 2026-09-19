import React, { useState } from 'react';
import { ChevronDown, ChevronUp, FileText, Sparkles, BookOpen } from 'lucide-react';
import { LegalClause } from '../../types';
import { Badge } from '../ui/Badge';

interface ClauseCardProps {
  clause: LegalClause;
  onSelect?: (clause: LegalClause) => void;
  isActive?: boolean;
}

export const ClauseCard: React.FC<ClauseCardProps> = ({
  clause,
  onSelect,
  isActive = false
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      id={`clause-card-${clause.id}`}
      onClick={() => onSelect?.(clause)}
      className={`p-4 rounded-xl transition-all duration-200 cursor-pointer border hover-float-sm ${
        isActive
          ? 'bg-indigo-950/40 border-indigo-500/80 shadow-md shadow-indigo-500/10 ring-1 ring-indigo-500/40'
          : 'bg-slate-900/70 border-slate-800/80 hover:border-indigo-500/40 hover:bg-slate-900/90'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-indigo-400 font-semibold px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">
              {clause.clauseNumber}
            </span>
            <span className="text-xs text-slate-400">
              Page {clause.page} • {clause.section}
            </span>
          </div>
          <h4 className="text-sm font-semibold text-white tracking-tight truncate">
            {clause.title}
          </h4>
        </div>

        <Badge variant={clause.attentionLevel} size="sm">
          {clause.attentionLevel === 'high' ? 'High Attention' :
           clause.attentionLevel === 'medium' ? 'Requires Attention' :
           clause.attentionLevel === 'low' ? 'Low Attention' : 'Informational'}
        </Badge>
      </div>

      {/* Plain English Summary */}
      <div className="mt-3 p-3 rounded-lg bg-black/40 border border-slate-800/80 space-y-1.5">
        <div className="flex items-center gap-1.5 text-xs text-indigo-300 font-medium">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>Plain English Translation:</span>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          {clause.plainSummary}
        </p>
      </div>

      {/* Potential concern warning if present */}
      {clause.potentialConcern && (
        <div className="mt-2 text-xs text-amber-300/90 flex items-start gap-1.5">
          <span className="font-semibold text-amber-400">•</span>
          <span>{clause.potentialConcern}</span>
        </div>
      )}

      {/* Toggle original legal wording */}
      <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-400">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
          className="flex items-center gap-1 hover:text-white transition-colors"
        >
          <BookOpen className="w-3 h-3 text-indigo-400" />
          <span>{isExpanded ? 'Hide Original Clause' : 'View Original Contract Text'}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        <span className="text-[11px] text-indigo-400 font-mono">
          {clause.category}
        </span>
      </div>

      {isExpanded && (
        <div 
          onClick={(e) => e.stopPropagation()} 
          className="mt-3 p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-400 leading-relaxed max-h-48 overflow-y-auto"
        >
          <p className="text-slate-300 font-semibold mb-1 text-[10px] uppercase tracking-wider">
            Original Text ({clause.section}):
          </p>
          "{clause.originalText}"
        </div>
      )}
    </div>
  );
};
