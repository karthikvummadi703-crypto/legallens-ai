import React from 'react';
import { AttentionLevel, DocumentStatus } from '../../types';

interface BadgeProps {
  variant?: AttentionLevel | DocumentStatus | 'neutral' | 'info' | 'success';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  children,
  className = '',
  icon
}) => {
  const getStyles = () => {
    switch (variant) {
      case 'high':
      case 'High Attention':
        return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
      case 'medium':
      case 'Needs Review':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
      case 'low':
      case 'Low Attention':
        return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
      case 'informational':
      case 'Analyzed':
      case 'info':
        return 'bg-sky-500/15 text-sky-300 border-sky-500/30';
      case 'Processing':
        return 'bg-violet-500/15 text-violet-300 border-violet-500/30 animate-pulse';
      case 'success':
        return 'bg-teal-500/15 text-teal-300 border-teal-500/30';
      default:
        return 'bg-slate-800/60 text-slate-300 border-slate-700/50';
    }
  };

  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5'
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border tracking-wide whitespace-nowrap ${getStyles()} ${sizeClasses[size]} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
};
