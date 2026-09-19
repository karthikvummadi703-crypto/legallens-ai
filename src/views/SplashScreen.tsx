import React, { useEffect, useState } from 'react';
import { Logo } from '../components/brand/Logo';
import { ShieldCheck, Sparkles, ArrowRight } from 'lucide-react';
import { AeroShards } from '../components/ui/AeroShards';

interface SplashScreenProps {
  onComplete: () => void;
}

export const SplashScreen: React.FC<SplashScreenProps> = ({ onComplete }) => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(onComplete, 300);
          return 100;
        }
        return prev + 4;
      });
    }, 80);

    return () => clearInterval(interval);
  }, [onComplete]);

  return (
    <div 
      id="legallens-splash-screen"
      className="fixed inset-0 z-50 bg-[#06080d] flex flex-col items-center justify-center p-6 select-none overflow-hidden"
    >
      {/* Animated AeroShards WebGPU Wind Sculpture Background */}
      <div className="absolute inset-0 z-0 pointer-events-auto">
        <AeroShards
          backgroundColor="#06080d"
          shardColor="#4338ca"
          accentColor="#6366f1"
          placement="center"
          flow="vortex"
          material="chrome"
          detail="balanced"
          scale={1.35}
          spread={0.88}
          depth={0.7}
          speed={0.65}
          spin={1.1}
          interaction="attract"
          density={1.35}
          shardSize={1.15}
          glow={1.6}
          bloom={1.0}
          grain={0.06}
          chromaticAberration={0.006}
          holdToGather={true}
        />
      </div>

      {/* Subtle Background Radial Overlay */}
      <div 
        className="absolute inset-0 z-[1] opacity-20 pointer-events-none" 
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgba(99, 102, 241, 0.25) 1px, transparent 0)`,
          backgroundSize: '36px 36px'
        }}
      />

      {/* Central Content */}
      <div className="relative z-10 flex flex-col items-center text-center max-w-md w-full animate-in fade-in zoom-in-95 duration-700 bg-[#06080d]/65 backdrop-blur-lg p-8 rounded-3xl border border-indigo-500/20 shadow-2xl shadow-black/80">
        {/* Large Animated Stylized L Logo */}
        <div className="mb-6 relative">
          <Logo size="xl" showText={false} animated={true} />
          <div className="absolute -inset-4 bg-indigo-500/20 blur-2xl rounded-full -z-10 animate-pulse" />
        </div>

        {/* Brand Name & Tagline */}
        <div className="space-y-2 mb-8">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
            Legal<span className="text-indigo-400">Lens</span> <span className="text-sm px-2 py-0.5 rounded font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">AI</span>
          </h1>

          <p className="text-xs uppercase tracking-[0.25em] text-indigo-300/80 font-semibold font-mono">
            LEGAL DOCUMENT INTELLIGENCE
          </p>

          <p className="text-sm text-slate-400 italic">
            "Understand before you sign."
          </p>
        </div>

        {/* Loading Progress Bar */}
        <div className="w-64 space-y-2 mb-6">
          <div className="h-1.5 w-full bg-slate-900/90 rounded-full overflow-hidden border border-slate-800">
            <div 
              className="h-full bg-gradient-to-r from-indigo-500 via-sky-400 to-violet-500 rounded-full transition-all duration-150 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between items-center text-[10px] font-mono text-slate-400">
            <span>INITIALIZING ENGINE</span>
            <span>{progress}%</span>
          </div>
        </div>

        {/* Skip button for rapid reviewer experience */}
        <button
          onClick={onComplete}
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-indigo-400 transition-colors py-1 px-3 rounded-lg hover:bg-slate-900/60"
        >
          <span>Skip to overview</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Safety Notice Footer */}
      <div className="absolute bottom-6 z-10 flex items-center gap-2 text-[11px] text-slate-400 bg-slate-950/70 backdrop-blur-sm px-3.5 py-1.5 rounded-full border border-slate-800/60">
        <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
        <span>Informational intelligence assistance • Not professional legal advice</span>
      </div>
    </div>
  );
};
