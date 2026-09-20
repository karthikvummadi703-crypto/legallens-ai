import React, { useState } from 'react';
import { 
  User, 
  ShieldCheck, 
  Sliders, 
  Bell, 
  HardDrive, 
  Key, 
  Cpu, 
  CheckCircle2, 
  Save,
  Lock,
  Download
} from 'lucide-react';
import { UserProfile } from '../types';
import { Button } from '../components/ui/Button';

interface SettingsPageProps {
  user: UserProfile;
  onUpdateUser: (user: UserProfile) => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ user, onUpdateUser }) => {
  const [name, setName] = useState(user?.name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [riskSensitivity, setRiskSensitivity] = useState<'conservative' | 'balanced' | 'flexible'>('conservative');
  const [autoChecklist, setAutoChecklist] = useState(true);
  const [notificationEmail, setNotificationEmail] = useState(true);
  const [plainLanguageLevel, setPlainLanguageLevel] = useState<'standard' | 'simple' | 'executive'>('simple');
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdateUser({
      ...user,
      name,
      email
    });
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div id="settings-view" className="p-4 sm:p-8 max-w-4xl mx-auto space-y-8 select-none">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
            Settings & Preferences
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Manage your account, legal risk tolerance parameters, and AI engine preferences.
          </p>
        </div>

        {saveSuccess && (
          <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-3 py-1.5 rounded-xl animate-in fade-in">
            <CheckCircle2 className="w-4 h-4" />
            <span>Settings saved successfully</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Account Profile Card */}
        <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center gap-2 text-indigo-400 border-b border-slate-800 pb-3">
            <User className="w-4 h-4" />
            <h3 className="text-sm font-bold text-white font-['Space_Grotesk']">Profile & Workspace Identity</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="settings-name" className="text-xs font-medium text-slate-300">Your Full Name</label>
              <input
                id="settings-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3.5 py-2 text-xs rounded-xl glass-input"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="settings-email" className="text-xs font-medium text-slate-300">Contact Email</label>
              <input
                id="settings-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2 text-xs rounded-xl glass-input"
              />
            </div>
          </div>
        </div>

        {/* AI & Risk Intelligence Calibration */}
        <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-5">
          <div className="flex items-center gap-2 text-indigo-400 border-b border-slate-800 pb-3">
            <Sliders className="w-4 h-4" />
            <h3 className="text-sm font-bold text-white font-['Space_Grotesk']">Legal Risk Sensitivity</h3>
          </div>

          <div className="space-y-3">
            <label className="text-xs text-slate-400">
              Select how aggressively LegalLens AI flags potential contractual risks:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { id: 'conservative', label: 'Conservative (Recommended)', desc: 'Highlights any clause with unilateral or aggressive terms.' },
                { id: 'balanced', label: 'Balanced Standard', desc: 'Highlights standard deviations from typical commercial norms.' },
                { id: 'flexible', label: 'Lenient / High-Tolerance', desc: 'Only flags severe non-competes and unbounded liabilities.' }
              ].map((lvl) => (
                <div
                  key={lvl.id}
                  onClick={() => setRiskSensitivity(lvl.id as any)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer space-y-1 hover-float-sm ${
                    riskSensitivity === lvl.id
                      ? 'bg-indigo-950/40 border-indigo-500/80 text-white shadow-sm'
                      : 'bg-slate-900/40 border-slate-800/80 text-slate-400 hover:border-indigo-500/40'
                  }`}
                >
                  <div className="text-xs font-semibold text-white">{lvl.label}</div>
                  <div className="text-[11px] text-slate-400 leading-relaxed">{lvl.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Plain English Language Tuning */}
          <div className="space-y-2 pt-2">
            <label className="text-xs font-medium text-slate-300">Plain English Simplification Level</label>
            <div className="flex items-center gap-2">
              {[
                { id: 'simple', label: 'Everyday Simple (Grade 8)' },
                { id: 'standard', label: 'Professional Plain English' },
                { id: 'executive', label: 'Executive Summary Brief' }
              ].map((lvl) => (
                <button
                  key={lvl.id}
                  type="button"
                  onClick={() => setPlainLanguageLevel(lvl.id as any)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer hover-float-pill ${
                    plainLanguageLevel === lvl.id
                      ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800 hover:border-slate-700'
                  }`}
                >
                  {lvl.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Security & Data Privacy Notice */}
        <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center gap-2 text-indigo-400 border-b border-slate-800 pb-3">
            <ShieldCheck className="w-4 h-4" />
            <h3 className="text-sm font-bold text-white font-['Space_Grotesk']">Privacy & Security</h3>
          </div>

          <div className="space-y-3 text-xs text-slate-300 leading-relaxed">
            <p className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>End-to-end document isolation: Your uploaded contracts are stored and analyzed securely by your authenticated backend workspace.</span>
            </p>
            <p className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-400 shrink-0" />
              <span>Powered by Gemini API with FastAPI extraction, RAG grounded answers, and vector-stored clause retrieval.</span>
            </p>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3 pt-2">
          <Button
            type="submit"
            variant="glow"
            size="md"
            leftIcon={<Save className="w-4 h-4" />}
          >
            Save Preferences
          </Button>
        </div>
      </form>
    </div>
  );
};
