import React from 'react';
import { AlertTriangle, ShieldAlert, ArrowRight, Lightbulb, FileSearch } from 'lucide-react';
import { RiskItem } from '../../types';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface RiskCardProps {
  risk: RiskItem;
  onViewClause?: (clauseRef: string) => void;
}

export const RiskCard: React.FC<RiskCardProps> = ({ risk, onViewClause }) => {
  const getAttentionLabel = () => {
    switch (risk.attentionLevel) {
      case 'high':
        return 'High Attention';
      case 'medium':
        return 'Requires Attention';
      case 'low':
        return 'Consider Reviewing';
      default:
        return 'Informational';
    }
  };

  return (
    <div
      id={`risk-card-${risk.id}`}
      className="p-5 rounded-2xl bg-slate-900/70 border border-slate-800 hover:border-indigo-500/40 transition-all duration-200 flex flex-col justify-between gap-4 group hover-float cursor-pointer"
    >
      <div className="space-y-3">
        {/* Top bar with category & attention level */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-0.5 rounded-md">
              {risk.category}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Page {risk.page} • {risk.section}
            </span>
          </div>

          <Badge variant={risk.attentionLevel} size="sm">
            {getAttentionLabel()}
          </Badge>
        </div>

        {/* Title */}
        <h4 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
          {risk.attentionLevel === 'high' ? (
            <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          )}
          <span>{risk.title}</span>
        </h4>

        {/* Description */}
        <p className="text-xs text-slate-300 leading-relaxed">
          {risk.description}
        </p>

        {/* Potential Impact Box */}
        <div className="p-3 rounded-xl bg-black/40 border border-slate-800/80 space-y-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Potential Concern & Impact
          </span>
          <p className="text-xs text-slate-300 leading-relaxed">
            {risk.potentialImpact}
          </p>
        </div>

        {/* Suggested Action */}
        <div className="flex items-start gap-2 text-xs text-indigo-300/90 pt-1">
          <Lightbulb className="w-3.5 h-3.5 shrink-0 text-amber-400 mt-0.5" />
          <span className="leading-snug">
            <strong>Recommended Step:</strong> {risk.suggestedAction}
          </span>
        </div>
      </div>

      {/* Footer Action */}
      {onViewClause && (
        <div className="pt-2 flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onViewClause(risk.clauseNumber)}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            className="text-xs text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10"
          >
            View Clause in Document
          </Button>
        </div>
      )}
    </div>
  );
};
