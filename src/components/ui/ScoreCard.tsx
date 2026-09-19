import React from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { Badge } from './Badge';

interface ScoreCardProps {
  score: number; // 0 to 100
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  showGauge?: boolean;
  className?: string;
}

export const ScoreCard: React.FC<ScoreCardProps> = ({
  score,
  label,
  size = 'md',
  showGauge = true,
  className = ''
}) => {
  // Determine severity tier
  let statusText = label;
  let colorClass = 'text-emerald-400';
  let strokeColor = '#10B981';
  let glowClass = 'glow-emerald';
  let Icon = CheckCircle;
  let badgeVariant: 'high' | 'medium' | 'low' | 'informational' = 'low';

  if (score >= 80) {
    statusText = statusText || 'High Attention';
    colorClass = 'text-rose-400';
    strokeColor = '#F43F5E';
    glowClass = 'glow-rose';
    Icon = ShieldAlert;
    badgeVariant = 'high';
  } else if (score >= 60) {
    statusText = statusText || 'Needs Review';
    colorClass = 'text-amber-400';
    strokeColor = '#F59E0B';
    glowClass = 'glow-amber';
    Icon = AlertTriangle;
    badgeVariant = 'medium';
  } else if (score >= 40) {
    statusText = statusText || 'Moderate';
    colorClass = 'text-sky-400';
    strokeColor = '#38BDF8';
    glowClass = 'glow-blue';
    Icon = Info;
    badgeVariant = 'informational';
  } else {
    statusText = statusText || 'Low Attention';
    colorClass = 'text-emerald-400';
    strokeColor = '#10B981';
    glowClass = 'glow-emerald';
    Icon = CheckCircle;
    badgeVariant = 'low';
  }

  // SVG circle calculation
  const radius = 32;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  if (size === 'sm') {
    return (
      <div className={`inline-flex items-center gap-2 ${className}`}>
        <div className="relative flex items-center justify-center w-9 h-9">
          <svg className="w-9 h-9 -rotate-90">
            <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
            <circle
              cx="18"
              cy="18"
              r="14"
              fill="none"
              stroke={strokeColor}
              strokeWidth="3"
              strokeDasharray={2 * Math.PI * 14}
              strokeDashoffset={2 * Math.PI * 14 - (score / 100) * 2 * Math.PI * 14}
              strokeLinecap="round"
            />
          </svg>
          <span className="absolute text-[11px] font-bold text-white font-mono">{score}</span>
        </div>
        <Badge variant={badgeVariant} size="sm">{statusText}</Badge>
      </div>
    );
  }

  return (
    <div className={`relative p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md flex items-center justify-between gap-4 ${glowClass} ${className}`}>
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
          Attention Score
        </span>
        <div className="flex items-baseline gap-2">
          <span className={`text-3xl font-extrabold font-['Space_Grotesk'] tracking-tight ${colorClass}`}>
            {score}
          </span>
          <span className="text-xs text-slate-500 font-medium">/ 100</span>
        </div>
        <div className="mt-1">
          <Badge variant={badgeVariant} size="md" icon={<Icon className="w-3 h-3" />}>
            {statusText}
          </Badge>
        </div>
      </div>

      {showGauge && (
        <div className="relative flex items-center justify-center shrink-0">
          <svg className="w-20 h-20 -rotate-90 transform">
            <circle
              cx="40"
              cy="40"
              r={radius}
              fill="transparent"
              stroke="rgba(255, 255, 255, 0.08)"
              strokeWidth="6"
            />
            <circle
              cx="40"
              cy="40"
              r={radius}
              fill="transparent"
              stroke={strokeColor}
              strokeWidth="6"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              className="transition-all duration-1000 ease-out"
            />
          </svg>
          <div className="absolute flex flex-col items-center justify-center">
            <Icon className={`w-5 h-5 ${colorClass}`} />
          </div>
        </div>
      )}
    </div>
  );
};
