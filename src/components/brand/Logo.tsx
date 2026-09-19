import React from 'react';

interface LogoProps {
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  showText?: boolean;
  showTagline?: boolean;
  animated?: boolean;
  className?: string;
  onClick?: () => void;
}

export const Logo: React.FC<LogoProps> = ({
  size = 'md',
  showText = true,
  showTagline = false,
  animated = false,
  className = '',
  onClick
}) => {
  const sizeMap = {
    xs: { icon: 24, text: 'text-sm', ai: 'text-[9px] px-1 py-0.2', gap: 'gap-1.5' },
    sm: { icon: 30, text: 'text-base', ai: 'text-[10px] px-1.5 py-0.5', gap: 'gap-2' },
    md: { icon: 38, text: 'text-lg', ai: 'text-[11px] px-1.5 py-0.5', gap: 'gap-2.5' },
    lg: { icon: 48, text: 'text-2xl', ai: 'text-xs px-2 py-0.5', gap: 'gap-3' },
    xl: { icon: 72, text: 'text-4xl', ai: 'text-sm px-2.5 py-1', gap: 'gap-4' }
  };

  const config = sizeMap[size];
  const iconSize = config.icon;

  return (
    <div 
      id="legallens-brand-logo"
      onClick={onClick}
      className={`inline-flex items-center select-none ${config.gap} ${onClick ? 'cursor-pointer' : ''} ${className}`}
    >
      {/* Stylized L + Lens Icon */}
      <div 
        className={`relative flex items-center justify-center shrink-0 ${animated ? 'transition-transform duration-300 hover:scale-105' : ''}`}
        style={{ width: iconSize, height: iconSize }}
      >
        {/* Ambient Glow */}
        <div 
          className="absolute inset-0 rounded-xl bg-gradient-to-tr from-indigo-600/40 via-blue-500/25 to-violet-600/40 blur-[10px] -z-10"
        />

        <svg
          width={iconSize}
          height={iconSize}
          viewBox="0 0 48 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="relative overflow-visible"
        >
          <defs>
            <linearGradient id="logo-lens-glow" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
              <stop stopColor="#6366F1" />
              <stop offset="0.5" stopColor="#38BDF8" />
              <stop offset="1" stopColor="#8B5CF6" />
            </linearGradient>

            <linearGradient id="logo-l-gradient" x1="12" y1="10" x2="36" y2="38" gradientUnits="userSpaceOnUse">
              <stop stopColor="#FFFFFF" />
              <stop offset="0.7" stopColor="#E0E7FF" />
              <stop offset="1" stopColor="#A5B4FC" />
            </linearGradient>

            <radialGradient id="lens-iris" cx="50%" cy="50%" r="50%">
              <stop stopColor="#6366f1" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#0b0f19" stopOpacity="0" />
            </radialGradient>

            <filter id="glow-filter" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Document / Lens Base Shield */}
          <rect
            x="4"
            y="4"
            width="40"
            height="40"
            rx="11"
            fill="#0B0F19"
            stroke="url(#logo-lens-glow)"
            strokeWidth="1.5"
            strokeOpacity="0.8"
          />

          {/* Lens Iris subtle circle */}
          <circle
            cx="24"
            cy="24"
            r="16"
            fill="url(#lens-iris)"
            stroke="rgba(99, 102, 241, 0.2)"
            strokeWidth="1"
            strokeDasharray="2 2"
          />

          {/* Optical crosshairs / ticks representing intelligence focus */}
          <line x1="24" y1="8" x2="24" y2="12" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.8" />
          <line x1="24" y1="36" x2="24" y2="40" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.8" />
          <line x1="8" y1="24" x2="12" y2="24" stroke="#8B5CF6" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.8" />
          <line x1="36" y1="24" x2="40" y2="24" stroke="#8B5CF6" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.8" />

          {/* Stylized Architectural 'L' fused with document perspective */}
          {/* Vertical Stem */}
          <path
            d="M 17 13 L 23 13 L 23 31 L 34 31 L 34 36 L 17 36 Z"
            fill="url(#logo-l-gradient)"
            filter="url(#glow-filter)"
          />

          {/* Precision AI Lens Point - Cyan Focal Dot */}
          <circle
            cx="34"
            cy="14"
            r="2.5"
            fill="#38BDF8"
            className={animated ? 'animate-pulse' : ''}
          />
        </svg>
      </div>

      {/* Brand Text */}
      {showText && (
        <div className="flex flex-col leading-tight">
          <div className="flex items-center gap-1.5">
            <span className={`font-semibold tracking-tight text-white ${config.text} font-['Space_Grotesk']`}>
              Legal<span className="text-indigo-400">Lens</span>
            </span>
            <span className={`rounded font-mono font-bold tracking-wider bg-gradient-to-r from-indigo-500/20 to-violet-500/20 text-indigo-300 border border-indigo-500/30 ${config.ai}`}>
              AI
            </span>
          </div>

          {showTagline && (
            <span className="text-[11px] font-medium tracking-wide text-slate-400">
              Understand before you sign.
            </span>
          )}
        </div>
      )}
    </div>
  );
};
