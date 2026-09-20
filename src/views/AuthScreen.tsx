import React, { useState } from 'react';
import { Mail, Lock, User, ArrowRight, CheckCircle2, AlertCircle, ArrowLeft, Eye, EyeOff } from 'lucide-react';
import { Logo } from '../components/brand/Logo';
import { Button } from '../components/ui/Button';
import { authService, getAuthErrorMessage } from '../services/authService';
import { UserProfile } from '../types';
import { AeroShards } from '../components/ui/AeroShards';

interface AuthScreenProps {
  onSuccess: (user: UserProfile) => void;
  onBackToIntro: () => void;
  initialMode?: 'login' | 'signup' | 'forgot';
}

export const AuthScreen: React.FC<AuthScreenProps> = ({
  onSuccess,
  onBackToIntro,
  initialMode = 'login'
}) => {
  const [mode, setMode] = useState<'login' | 'signup' | 'forgot'>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [resetSuccessMsg, setResetSuccessMsg] = useState<string | null>(null);
  const [showResend, setShowResend] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleResendVerification = async () => {
    try {
      // Re-login temporarily to get a user object for resend, then sign out
      // Simpler: Firebase keeps no session here (we signed out), so ask user
      // to sign in once after verifying; resend works if they just signed up.
      // Best-effort: try current user, else prompt to check inbox.
      await authService.resendVerification();
      setResetSuccessMsg('Verification link re-sent. Check your inbox (and spam).');
      setErrorMsg(null);
    } catch {
      setErrorMsg('Could not resend right now. Try signing in once to trigger a new link.');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setResetSuccessMsg(null);
    setShowResend(false);
    setIsLoading(true);

    try {
      if (mode === 'login') {
        if (!email) {
          setErrorMsg('Please provide a valid email address.');
          setIsLoading(false);
          return;
        }
        const res = await authService.login(email, password);
        onSuccess(res.user);
      } else if (mode === 'signup') {
        if (!name || !email) {
          setErrorMsg('All fields are required.');
          setIsLoading(false);
          return;
        }
        if (password !== confirmPassword) {
          setErrorMsg('Passwords do not match.');
          setIsLoading(false);
          return;
        }
        const res = await authService.signup(name, email, password);
        // Email/password: do NOT log in — require verification click first
        if (res.needsVerification) {
          setResetSuccessMsg(
            `Account created for ${res.user.email}! Click the activation link in your inbox to activate it, then sign in.`
          );
          setMode('login');
          setPassword('');
          setConfirmPassword('');
          return;
        }
        onSuccess(res.user);
      } else if (mode === 'forgot') {
        if (!email) {
          setErrorMsg('Please enter your email.');
          setIsLoading(false);
          return;
        }
        const res = await authService.resetPassword(email);
        setResetSuccessMsg(res.message);
      }
    } catch (err) {
      setErrorMsg(getAuthErrorMessage(err));
      // Show "Resend link" only for unverified email/password logins
      if (typeof err === 'object' && err !== null && 'code' in err &&
          (err as { code?: string }).code === 'auth/email-not-verified') {
        setShowResend(true);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setErrorMsg(null);
    setResetSuccessMsg(null);
    setIsLoading(true);
    try {
      const res = await authService.loginWithGoogle();
      onSuccess(res.user);
    } catch (err) {
      setErrorMsg(getAuthErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div 
      id="legallens-auth-screen"
      className="min-h-screen bg-[#05070c] text-slate-100 flex flex-col justify-center items-center p-6 relative overflow-hidden select-none"
    >
      {/* Interactive Animated Background */}
      <div className="absolute inset-0 z-0 pointer-events-auto opacity-70">
        <AeroShards
          backgroundColor="#05070c"
          shardColor="#4338ca"
          accentColor="#6366f1"
          placement="center"
          flow="vortex"
          material="chrome"
          detail="balanced"
          scale={1.3}
          spread={0.9}
          depth={0.7}
          speed={0.5}
          spin={1.0}
          interaction="attract"
          density={1.25}
          shardSize={1.1}
          glow={1.5}
          bloom={0.9}
          grain={0.05}
          chromaticAberration={0.006}
          holdToGather={true}
        />
      </div>

      {/* Background ambient lighting */}
      <div className="absolute w-[600px] h-[600px] bg-indigo-600/10 blur-[140px] rounded-full pointer-events-none -top-32 z-[1]" />
      <div className="absolute w-[400px] h-[400px] bg-violet-600/10 blur-[120px] rounded-full pointer-events-none -bottom-20 z-[1]" />

      {/* Back button */}
      <div className="absolute top-6 left-6 z-20">
        <button
          onClick={onBackToIntro}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors p-2 rounded-xl hover:bg-slate-800/60"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to overview</span>
        </button>
      </div>

      <div className="relative z-10 w-full max-w-md p-8 rounded-3xl bg-[#090d16]/80 backdrop-blur-xl border border-slate-700/60 shadow-2xl space-y-6">
        {/* Header Branding */}
        <div className="text-center space-y-2">
          <div className="inline-block mb-1">
            <Logo size="lg" showText={true} />
          </div>
          <div className="text-[10px] font-mono tracking-widest text-indigo-400 font-bold uppercase">
            Legal Document Intelligence
          </div>
          <p className="text-xs text-slate-400 italic">
            Understand before you sign.
          </p>
        </div>

        {/* Error / Success Notifications */}
        {errorMsg && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span>{errorMsg}</span>
              {showResend && (
                <button
                  type="button"
                  onClick={handleResendVerification}
                  className="block mt-1.5 text-indigo-300 hover:text-indigo-200 font-semibold underline underline-offset-2"
                >
                  Resend verification link
                </button>
              )}
            </div>
          </div>
        )}

        {resetSuccessMsg && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{resetSuccessMsg}</span>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'signup' && (
            <div className="space-y-1.5">
              <label htmlFor="auth-name" className="text-xs font-semibold text-slate-300">Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="auth-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your full name"
                  className="w-full pl-9 pr-4 py-2 text-xs rounded-xl glass-input"
                  required
                />
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="auth-email" className="text-xs font-semibold text-slate-300">Work Email</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full pl-9 pr-4 py-2 text-xs rounded-xl glass-input"
                required
              />
            </div>
          </div>

          {mode !== 'forgot' && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="auth-password" className="text-xs font-semibold text-slate-300">Password</label>
                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => {
                      setErrorMsg(null);
                      setMode('forgot');
                    }}
                    className="text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="auth-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-10 py-2 text-xs rounded-xl glass-input"
                  required
                  minLength={6}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
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
          )}

          {mode === 'signup' && (
            <div className="space-y-1.5">
              <label htmlFor="auth-confirm" className="text-xs font-semibold text-slate-300">Confirm Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="auth-confirm"
                  type={showConfirmPassword ? 'text' : 'password'}
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
                  onClick={() => setShowConfirmPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-200 transition-colors"
                  title={showConfirmPassword ? 'Hide password' : 'Show password'}
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          )}

          <Button
            type="submit"
            variant="glow"
            size="md"
            isLoading={isLoading}
            className="w-full mt-2 text-xs font-semibold"
          >
            {mode === 'login' && 'Sign In'}
            {mode === 'signup' && 'Create Account'}
            {mode === 'forgot' && 'Send Reset Link'}
          </Button>
        </form>

        {/* Divider & Google OAuth Button */}
        {mode !== 'forgot' && (
          <>
            <div className="relative my-5">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-800" />
              </div>
              <div className="relative flex justify-center text-[10px] uppercase font-mono tracking-wider">
                <span className="bg-[#0c101a] px-3 text-slate-500">Or continue with</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2.5 py-2 px-4 rounded-xl bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>Continue with Google</span>
            </button>
          </>
        )}

        {/* Switch between modes */}
        <div className="mt-6 text-center text-xs text-slate-400">
          {mode === 'login' && (
            <p>
              Don't have an account?{' '}
              <button
                onClick={() => {
                  setErrorMsg(null);
                  setMode('signup');
                }}
                className="text-indigo-400 hover:text-indigo-300 font-medium"
              >
                Sign up
              </button>
            </p>
          )}

          {mode === 'signup' && (
            <p>
              Already have an account?{' '}
              <button
                onClick={() => {
                  setErrorMsg(null);
                  setMode('login');
                }}
                className="text-indigo-400 hover:text-indigo-300 font-medium"
              >
                Sign in
              </button>
            </p>
          )}

          {mode === 'forgot' && (
            <button
              onClick={() => {
                setErrorMsg(null);
                setMode('login');
              }}
              className="text-indigo-400 hover:text-indigo-300 font-medium"
            >
              Return to Sign In
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
