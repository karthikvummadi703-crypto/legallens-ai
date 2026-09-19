import React from 'react';
import { FileText, Calendar, HardDrive, ArrowUpRight, Trash2, CheckCircle2 } from 'lucide-react';
import { LegalDocument } from '../../types';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface DocumentCardProps {
  document: LegalDocument;
  onSelect: (doc: LegalDocument) => void;
  onAnalyze: (doc: LegalDocument) => void;
  onDelete?: (id: string) => void;
  isSelected?: boolean;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  onSelect,
  onAnalyze,
  onDelete,
  isSelected = false
}) => {
  return (
    <div
      id={`doc-card-${document.id}`}
      className={`group relative p-5 rounded-2xl transition-all duration-300 flex flex-col justify-between glass-panel-interactive hover-float ${
        isSelected ? 'border-indigo-500/80 bg-slate-900/90 shadow-lg shadow-indigo-500/15 ring-1 ring-indigo-500/40' : ''
      }`}
    >
      {/* Header Info */}
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0 text-indigo-400 group-hover:scale-105 transition-transform">
              <FileText className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h3 
                onClick={() => onSelect(document)}
                className="text-sm font-semibold text-white tracking-tight truncate hover:text-indigo-300 cursor-pointer transition-colors"
                title={document.name}
              >
                {document.name}
              </h3>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-400">
                <span className="font-mono text-[11px] text-slate-400">{document.type}</span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {document.uploadDate}
                </span>
              </div>
            </div>
          </div>

          <Badge variant={document.analysisStatus} size="sm">
            {document.analysisStatus}
          </Badge>
        </div>

        {/* Short Summary */}
        <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
          {document.summary}
        </p>
      </div>

      {/* Metrics & Actions Footer */}
      <div className="pt-4 mt-4 border-t border-slate-800/80 space-y-3">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-3 text-slate-400">
            <span className="flex items-center gap-1">
              <HardDrive className="w-3 h-3" />
              {document.size}
            </span>
            <span>•</span>
            <span>{document.pageCount} pages</span>
          </div>

          <div className="flex items-center gap-1.5 font-medium">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider">Score:</span>
            <span className={`font-mono font-bold ${
              document.attentionScore >= 80 ? 'text-rose-400' :
              document.attentionScore >= 60 ? 'text-amber-400' : 'text-emerald-400'
            }`}>
              {document.attentionScore}/100
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSelect(document)}
              className="text-xs"
            >
              Open
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => onAnalyze(document)}
              rightIcon={<ArrowUpRight className="w-3.5 h-3.5" />}
              className="text-xs"
            >
              Analyze
            </Button>
          </div>

          {onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(document.id);
              }}
              title="Delete Document"
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
