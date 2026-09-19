import React, { useState } from 'react';
import { 
  Sparkles, 
  ArrowRight, 
  FileText, 
  Brain, 
  CheckCircle2, 
  ShieldAlert, 
  Search, 
  GitCompare, 
  FileSearch, 
  Scale, 
  HelpCircle,
  Play,
  Layers
} from 'lucide-react';
import { Logo } from '../components/brand/Logo';
import { Button } from '../components/ui/Button';
import { TrustBanner } from '../components/common/TrustBanner';
import { AeroShards } from '../components/ui/AeroShards';

interface IntroScreenProps {
  onGetStarted: () => void;
  onLogin: () => void;
}

export const IntroScreen: React.FC<IntroScreenProps> = ({ onGetStarted, onLogin }) => {
  const [activeTab, setActiveTab] = useState<'flow' | 'demo'>('flow');

  const features = [
    {
      icon: Scale,
      title: 'Simplify',
      desc: 'Turn complicated legal language into plain English with instant executive summaries.',
      accent: 'from-blue-500/20 to-indigo-500/20 border-indigo-500/30 text-indigo-400'
    },
    {
      icon: ShieldAlert,
      title: 'Spot Risks',
      desc: 'Identify clauses that may deserve closer attention, such as aggressive clawbacks or non-competes.',
      accent: 'from-rose-500/20 to-amber-500/20 border-amber-500/30 text-amber-400'
    },
    {
      icon: HelpCircle,
      title: 'Ask Questions',
      desc: 'Ask conversational questions about your uploaded documents with grounded source citations.',
      accent: 'from-violet-500/20 to-purple-500/20 border-violet-500/30 text-violet-400'
    },
    {
      icon: GitCompare,
      title: 'Compare',
      desc: 'Compare two contracts side by side to surface newly added obligations or modified terms.',
      accent: 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30 text-teal-400'
    }
  ];

  return (
    <div 
      id="legallens-intro-screen"
      className="min-h-screen bg-[#07090e] text-slate-100 flex flex-col justify-between selection:bg-indigo-500/30 relative overflow-hidden"
    >
      {/* Animated AeroShards WebGPU Background */}
      <div className="absolute inset-0 z-0 pointer-events-auto">
        <AeroShards
          backgroundColor="#07090e"
          shardColor="#4f46e5"
          accentColor="#8b5cf6"
          placement="full"
          flow="stream"
          material="chrome"
          detail="balanced"
          scale={1.3}
          spread={1.05}
          depth={0.65}
          speed={0.5}
          spin={1.0}
          interaction="repel"
          density={1.35}
          shardSize={1.15}
          stretch={1.05}
          turbulence={1.6}
          glow={1.6}
          bloom={1.0}
          grain={0.06}
          chromaticAberration={0.007}
          holdToGather={true}
        />
      </div>

      {/* Background ambient lighting */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-indigo-600/10 blur-[130px] rounded-full pointer-events-none z-[1]" />
      <div className="absolute top-1/3 -right-40 w-[500px] h-[500px] bg-violet-600/10 blur-[140px] rounded-full pointer-events-none z-[1]" />

      {/* Top Navbar */}
      <header className="relative z-10 max-w-7xl mx-auto w-full px-6 py-6 flex items-center justify-between border-b border-slate-800/60">
        <Logo size="md" showTagline={true} />

        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogin}
            className="text-xs"
          >
            Sign In
          </Button>
          <Button
            variant="glow"
            size="sm"
            onClick={onGetStarted}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            className="text-xs"
          >
            Launch Workspace
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 max-w-6xl mx-auto w-full px-6 py-12 lg:py-16 flex-1 flex flex-col items-center text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs font-semibold mb-6 shadow-sm">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>AI-Powered Legal Document Intelligence</span>
        </div>

        {/* Hero Title & Subtitle */}
        <h1 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight font-['Space_Grotesk'] max-w-3xl leading-[1.1]">
          Understand before <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-sky-300 to-violet-400">you sign.</span>
        </h1>

        <p className="mt-5 text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed">
          Turn complex legal documents into clear insights, potential risks, obligations, and actionable questions.
        </p>

        {/* CTA Buttons */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <Button
            variant="glow"
            size="lg"
            onClick={onGetStarted}
            rightIcon={<ArrowRight className="w-4 h-4" />}
          >
            Get Started
          </Button>
          <Button
            variant="secondary"
            size="lg"
            onClick={() => {
              const el = document.getElementById('how-it-works-visual');
              el?.scrollIntoView({ behavior: 'smooth' });
            }}
            leftIcon={<Play className="w-4 h-4 text-indigo-400 fill-indigo-400/20" />}
          >
            See How It Works
          </Button>
        </div>

        {/* Hero Visual: Document -> AI Analysis -> Insights */}
        <div 
          id="how-it-works-visual"
          className="mt-14 w-full rounded-2xl glass-panel p-6 sm:p-8 border border-slate-700/60 shadow-2xl relative overflow-hidden text-left"
        >
          {/* Subtle top glow line */}
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-indigo-500 via-sky-400 to-violet-500 opacity-60" />

          <div className="flex flex-col md:flex-row items-center justify-between gap-6 relative">
            {/* Step 1: Legal Document */}
            <div className="flex-1 w-full p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3 hover-float-sm cursor-default">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono text-indigo-400 font-semibold uppercase">
                  1. Document
                </span>
                <span className="text-[11px] text-slate-400 font-mono">14 Pages • PDF</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0 border border-indigo-500/20">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-white truncate">Employment_Agreement.pdf</p>
                  <p className="text-[11px] text-slate-400">Dense legal boilerplate</p>
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-black/40 border border-slate-800/80 text-[11px] font-mono text-slate-400 leading-snug line-clamp-2">
                "Section 8.1 Liquidated Damages on Early Departure... repayment of $45,000 within thirty (30) days..."
              </div>
            </div>

            {/* Connecting Flow Arrow / AI Brain */}
            <div className="flex flex-col items-center justify-center shrink-0 px-2 hover-float-sm cursor-default">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 animate-pulse">
                <Brain className="w-6 h-6" />
              </div>
              <span className="text-[10px] font-mono text-indigo-300 font-semibold uppercase tracking-wider mt-1.5">
                AI Engine
              </span>
            </div>

            {/* Step 2: Insights Produced */}
            <div className="flex-1 w-full p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/40 space-y-3 hover-float-sm cursor-default">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono text-indigo-300 font-semibold uppercase">
                  2. Plain English Insights
                </span>
                <span className="text-[11px] font-bold text-amber-300 bg-amber-500/15 px-2 py-0.5 rounded border border-amber-500/30">
                  Score: 72/100
                </span>
              </div>
              <div className="space-y-2">
                <div className="flex items-start gap-2 text-xs text-slate-200">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span><strong>Early exit clawback:</strong> Leaving within 12 months requires $45k repayment.</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-slate-200">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                  <span><strong>60-day unpaid notice:</strong> Unilateral administrative leave clause detected.</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 4 Feature Cards Grid */}
        <div className="mt-14 w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 text-left">
          {features.map((feat, i) => {
            const Icon = feat.icon;
            return (
              <div
                key={i}
                className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-indigo-500/50 flex flex-col justify-between gap-3 group hover-float cursor-pointer"
              >
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center border ${feat.accent}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-semibold text-white tracking-tight font-['Space_Grotesk']">
                    {feat.title}
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {feat.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Small Trust/Safety Statement */}
        <div className="mt-12 w-full max-w-xl">
          <TrustBanner variant="compact" className="justify-center" />
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 max-w-7xl mx-auto w-full px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-slate-800/60 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span>© 2026 LegalLens AI.</span>
          <span>•</span>
          <span>Understand before you sign.</span>
        </div>
        <div className="flex items-center gap-4 text-slate-400">
          <button onClick={onGetStarted} className="hover:text-white transition-colors">Workspace</button>
          <span>•</span>
          <button onClick={onLogin} className="hover:text-white transition-colors">Sign In</button>
        </div>
      </footer>
    </div>
  );
};
