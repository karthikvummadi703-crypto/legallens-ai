import React from 'react';
import { ShieldCheck, Info } from 'lucide-react';

interface TrustBannerProps {
  className?: string;
  variant?: 'compact' | 'full';
}

export const TrustBanner: React.FC<TrustBannerProps> = ({ 
  className = '',
  variant = 'compact'
}) => {
  if (variant === 'compact') {
    return (
      <div 
        id="legal-safety-trust-banner"
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-950/30 border border-indigo-500/20 text-indigo-300/90 text-xs ${className}`}
      >
        <ShieldCheck className="w-3.5 h-3.5 shrink-0 text-indigo-400" />
        <span className="truncate">
          <strong>Legal Safety:</strong> LegalLens provides informational assistance and does not replace professional legal advice.
        </span>
      </div>
    );
  }

  return (
    <div 
      id="legal-safety-trust-banner-full"
      className={`relative p-4 rounded-xl bg-slate-900/60 border border-indigo-500/20 backdrop-blur-sm flex items-start gap-3.5 text-xs text-slate-300 ${className}`}
    >
      <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
        <ShieldCheck className="w-4 h-4" />
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h4 className="font-semibold text-white tracking-tight">Legal Disclaimer & Informational Assistance</h4>
          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
            Safety Standard
          </span>
        </div>
        <p className="text-slate-400 leading-relaxed">
          LegalLens AI synthesizes and extracts patterns from uploaded documentation for informational purposes only. AI output does not constitute binding legal counsel, an attorney-client relationship, or formal legal certification. Always review critical contracts with qualified legal professionals.
        </p>
      </div>
    </div>
  );
};
