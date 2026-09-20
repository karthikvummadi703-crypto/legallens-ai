import React, { useEffect, useState } from 'react';
import { CheckCircle2, AlertCircle, Lock, Eye, EyeOff, ArrowRight } from 'lucide-react';
import { Logo } from '../components/brand/Logo';
import { Button } from '../components/ui/Button';
import { authService, getAuthErrorMessage } from '../services/authService';
import { AeroShards } from '../components/ui/AeroShards';

interface AuthActionHandlerProps {
  mode: 'verifyEmail' | 'resetPassword' | null;
  oobCode: string | null;
  onComplete: () => void;
}

type Phase = 'working' | 'verifySuccess' | 'verifyError' | 'resetForm' | 'resetSuccess' | 'resetError';

/**
 * Handles the action links that Firebase sends in email-verification and
 * password-reset emails. Because we send those emails with handleCodeInApp,
 * clicking the link returns the browser HERE with ?mode=...&oobCode=... so we
 * redeem the code inside the app instead of on Firebase's hosted page (which
 * can show "expired"/"error" for localhost dev and prefetched links).
 */
export const AuthActionHandler: React.FC<AuthActionHandlerProps> = ({ mode, oobCode, onComplete }) => {
  const [phase, setPhase] = useState<Phase>('working');
  const [message, setMessage] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    if (mode === 'verifyEmail' && oobCode) {
      authService
        .verifyEmailAction(oobCode)
        .then(() => setPhase('verifySuccess'))
        .catch((err) => {
          setMessage(getAuthErrorMessage(err));
          setPhase('verifyError');
        });
    } else if (mode === 'resetPassword' && oobCode) {
      setPhase('resetForm');
    } else {
      onComplete();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPassword || newPassword.length < 6) {
      setMessage('Please enter a new password with at least 6 characters.');
      setPhase('resetError');
      return;
    }
    if (newPassword !== confirmPassword) {
      setMessage('Passwords do not match.');
      setPhase('resetError');
      return;
    }
    if (!oobCode) {
      setMessage('This link is missing its code. Please request a new one.');
      setPhase('resetError');
      return;
    }
    setPhase('working');
    try {
      await authService.confirmPasswordReset(oobCode, newPassword);
      setPhase('resetSuccess');
    } catch (err) {
      setMessage(getAuthErrorMessage(err));
      setPhase('resetError');
    }
  };

  const success = phase === 'verifySuccess' || phase === 'resetSuccess';

  return (
    <div
      id="legallens-auth-action"
      className="min-h-screen bg-[#05070c] text-slate-100 flex flex-col justify-center items-center p-6 relative overflow-hidden select-none"
    >
      <div className="absolute inset-0 z-0 pointer-events-none opacity-50">
        <AeroShards
          backgroundColor="#05070c"
          shardColor="#4338ca"
          accentColor="#6366f1"
          placement="center"
          flow="vortex"
          material="chrome"
          detail="balanced"
          scale={1.2}
          spread={0.9}
          depth={0.7}
          speed={0.5}
          spin={1.0}
          interaction="attract"
          density={1.1}
          shardSize={1.0}
          glow={1.4}
          bloom={0.8}
          grain={0.05}
          chromaticAberration={0.006}
          holdToGather={true}
        />
      </div>
      <div className="relative z-10 w-full max-w-md p-8 rounded-3xl bg-[#090d16]/85 backdrop-blur-xl border border-slate-700/60 shadow-2xl space-y-6 text-center">
        <div className="text-center space-y-2">
          <div className="inline-block mb-1">
            <Logo size="lg" showText={true} />
          </div>
          <div className="text-[10px] font-mono tracking-widest text-indigo-400 font-bold uppercase">
            Legal Document Intelligence
          </div>
        </div>

        {phase === 'working' && (
          <div className="flex flex-col items-center gap-3 py-8">
            <div className="w-8 h-8 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400">Processing your link…</p>
          </div>
        )}

        {(phase === 'verifySuccess' || phase === 'resetSuccess') && (
          <>
            <div className="flex justify-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-400" />
            </div>
            <p className="text-sm font-semibold text-white">
              {phase === 'verifySuccess' ? 'Email verified!' : 'Password changed!'}
            </p>
            <p className="text-xs text-slate-400">
              {phase === 'verifySuccess'
                ? 'Your account is now active. You can sign in.'
                : 'Your password has been updated. Please sign in with your new password.'}
            </p>
            <Button variant="glow" size="md" className="w-full text-xs font-semibold" onClick={onComplete}>
              Continue to Sign In <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </>
        )}

        {(phase === 'verifyError' || phase === 'resetError') && !success && (
          <div className="flex flex-col items-center gap-3 py-4">
            <div className="flex justify-center">
              <AlertCircle className="w-10 h-10 text-rose-400" />
            </div>
            <p className="text-sm font-semibold text-white">We couldn't complete that</p>
            <p className="text-xs text-rose-300">{message}</p>
            <Button variant="glow" size="md" className="w-full text-xs font-semibold" onClick={onComplete}>
              Go to Sign In
            </Button>
          </div>
        )}

        {phase === 'resetForm' && (
          <form onSubmit={handleReset} className="space-y-4 text-left">
            <p className="text-xs text-slate-400">
              Choose a new password for your account, then sign in.
            </p>
            <div className="space-y-1.5">
              <label htmlFor="reset-password" className="text-xs font-semibold text-slate-300">New Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="reset-password"
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-10 py-2 text-xs rounded-xl glass-input"
                  required
                  minLength={6}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-200 transition-colors"
                  title={showPassword ? 'Hide password' : 'Show password'}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="reset-confirm" className="text-xs font-semibold text-slate-300">Confirm New Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="reset-confirm"
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-10 py-2 text-xs rounded-xl glass-input"
                  required
                  minLength={6}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-200 transition-colors"
                  title={showConfirm ? 'Hide password' : 'Show password'}
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            {message && phase === 'resetError' && (
              <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{message}</span>
              </div>
            )}
            <Button type="submit" variant="glow" size="md" className="w-full text-xs font-semibold">
              Set New Password
            </Button>
          </form>
        )}
      </div>
    </div>
  );
};