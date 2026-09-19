/**
 * Auth Service — Firebase Authentication
 *
 * Replaces the previous mock implementation with real Firebase Auth.
 * Supports: email/password login, signup, Google OAuth, password reset, logout.
 *
 * The app gracefully degrades if Firebase is not yet configured (env vars missing).
 */

import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  sendPasswordResetEmail,
  sendEmailVerification,
  signOut,
  updateProfile,
  onAuthStateChanged,
  applyActionCode,
  checkActionCode,
  confirmPasswordReset,
  type User,
} from 'firebase/auth';
import { auth } from '../lib/firebase';
import { UserProfile } from '../types';

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Convert a Firebase User object into our app's UserProfile shape. */
function toUserProfile(user: User): UserProfile {
  const provider = user.providerData?.[0]?.providerId ?? 'password';
  return {
    id: user.uid,
    name: user.displayName ?? user.email?.split('@')[0] ?? 'LegalLens User',
    email: user.email ?? '',
    role: 'Legal Professional',
    avatarUrl: user.photoURL ?? undefined,
    plan: 'Enterprise Pro',
    emailVerified: user.emailVerified,
    provider,
  };
}

export interface AuthResponse {
  user: UserProfile;
  token: string;
  needsVerification?: boolean;
}

// ─── Error Handling ───────────────────────────────────────────────────────────

/** Maps Firebase `auth/...` error codes to user-friendly messages. */
export function getAuthErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'code' in error) {
    const code = (error as { code?: string }).code;
    switch (code) {
      case 'auth/invalid-email':
        return 'That email address looks invalid. Please check and try again.';
      case 'auth/user-not-found':
        return 'No account found with this email. Please create an account first.';
      case 'auth/wrong-password':
        return 'Incorrect password. Please try again or use "Forgot password?".';
      case 'auth/invalid-credential':
        return 'Invalid email or password. Please try again.';
      case 'auth/email-already-in-use':
        return 'An account already exists with this email. Try signing in instead.';
      case 'auth/weak-password':
        return 'Password is too weak. Please use at least 6 characters.';
      case 'auth/too-many-requests':
        return 'Too many attempts. Please wait a moment and try again.';
      case 'auth/network-request-failed':
        return 'Network error. Check your connection and try again.';
      case 'auth/operation-not-allowed':
        return 'Email/password sign-in is not enabled. Contact support.';
      case 'auth/popup-closed-by-user':
      case 'auth/cancelled-popup-request':
        return 'Sign-in was cancelled. Please try again.';
      case 'auth/popup-blocked':
        return 'The sign-in popup was blocked. Allow popups for this site and try again.';
      case 'auth/unauthorized-domain':
        return 'This domain is not authorized for Google sign-in. Add it in the Firebase console.';
      case 'auth/user-disabled':
        return 'This account has been disabled. Contact support.';
      case 'auth/account-exists-with-different-credential':
        return 'An account already exists with this email using a different sign-in method. Try signing in with email instead.';
      case 'auth/email-not-verified':
        return 'Please verify your email first. Check your inbox for the activation link, then sign in.';
      case 'auth/invalid-action-code':
        return 'This link has expired or is invalid. Please request a new one.';
      case 'auth/expired-action-code':
        return 'This link has expired. Please request a new one.';
      default:
        return 'An unexpected error occurred. Please try again.';
    }
  }
  return 'An unexpected error occurred. Please try again.';
}

// ─── Auth Service ─────────────────────────────────────────────────────────────

export const authService = {
  /**
   * Returns the currently authenticated user, or null if not signed in.
   */
  async getCurrentUser(): Promise<UserProfile | null> {
    const user = auth.currentUser;
    if (!user) return null;
    return toUserProfile(user);
  },

  /**
   * Sign in with email and password.
   * Email/password accounts must be verified first. Google users bypass this
   * check entirely (handled in loginWithGoogle, never sent a link).
   */
  async login(email: string, password: string): Promise<AuthResponse> {
    const credential = await signInWithEmailAndPassword(auth, email, password);
    await credential.user.reload();
    const isPasswordProvider = credential.user.providerData.some(
      (p) => p.providerId === 'password'
    );
    // Only enforce verification for email/password accounts
    if (isPasswordProvider && !credential.user.emailVerified) {
      try {
        await sendEmailVerification(credential.user);
      } catch {
        // resend may be rate-limited; ignore, user can use Resend button
      }
      await signOut(auth);
      throw { code: 'auth/email-not-verified' };
    }
    const token = await credential.user.getIdToken();
    return { user: toUserProfile(credential.user), token };
  },

  /**
   * Create a new account with email and password.
   * Sends a verification link and does NOT activate the session until the
   * user clicks it. Caller must show "check inbox" instead of logging in.
   */
  async signup(name: string, email: string, password: string): Promise<AuthResponse> {
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    if (name) {
      await updateProfile(credential.user, { displayName: name });
    }
    // Email/password only: send activation link. handleCodeInApp:true means the
    // link returns to THIS app with ?oobCode=..., which we redeem via
    // verifyEmailAction() instead of relying on the Firebase hosted page
    // (that page can fail on localhost / get its code consumed by prefetch).
    await sendEmailVerification(credential.user, {
      url: window.location.origin,
      handleCodeInApp: true,
    });
    const user: UserProfile = {
      id: credential.user.uid,
      name: name || credential.user.displayName || email.split('@')[0] || 'LegalLens User',
      email: credential.user.email ?? email,
      role: 'Legal Professional',
      avatarUrl: credential.user.photoURL ?? undefined,
      plan: 'Enterprise Pro',
    };
    // Sign out immediately so unverified user cannot use the app
    await signOut(auth);
    return { user, token: '', needsVerification: true };
  },

  /**
   * Resend the activation link to the currently-signed-in (or just-created)
   * email/password user. No-op for Google users.
   */
  async resendVerification(): Promise<void> {
    const user = auth.currentUser;
    if (user && !user.emailVerified) {
      await sendEmailVerification(user, {
        url: window.location.origin,
        handleCodeInApp: true,
      });
    }
  },

  /**
   * Sign in (or sign up) with Google via a popup window.
   * Errors are propagated to the caller so the UI can show the real reason.
   */
  async loginWithGoogle(): Promise<AuthResponse> {
    const provider = new GoogleAuthProvider();
    provider.addScope('email');
    provider.addScope('profile');
    const credential = await signInWithPopup(auth, provider);
    const token = await credential.user.getIdToken();
    return { user: toUserProfile(credential.user), token };
  },

  /**
   * Send a password reset email.
   */
  async resetPassword(email: string): Promise<{ success: boolean; message: string }> {
    await sendPasswordResetEmail(auth, email, {
      url: window.location.origin,
      handleCodeInApp: true,
    });
    return {
      success: true,
      message: `Password reset instructions have been sent to ${email}.`,
    };
  },

  /**
   * Redeem an email-verification oobCode that Firebase returned to us via the
   * "Continue to app" link (handleCodeInApp). Validates then applies it.
   */
  async verifyEmailAction(oobCode: string): Promise<void> {
    const info = await checkActionCode(auth, oobCode);
    if (info.operation !== 'VERIFY_EMAIL') {
      throw { code: 'auth/invalid-action-code' };
    }
    await applyActionCode(auth, oobCode);
  },

  /**
   * Redeem a password-reset oobCode that Firebase returned to us, setting a
   * new password. A fresh sign-in is then required.
   */
  async confirmPasswordReset(oobCode: string, newPassword: string): Promise<void> {
    await confirmPasswordReset(auth, oobCode, newPassword);
  },

  /**
   * Sign out the current user.
   */
  async logout(): Promise<void> {
    await signOut(auth);
  },

  /**
   * Subscribe to auth state changes.
   * Returns the unsubscribe function — call it to clean up on unmount.
   */
  onAuthStateChanged(callback: (user: UserProfile | null) => void): () => void {
    return onAuthStateChanged(auth, (firebaseUser) => {
      callback(firebaseUser ? toUserProfile(firebaseUser) : null);
    });
  },
};
