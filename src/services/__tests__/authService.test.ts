import { describe, expect, it, vi } from 'vitest';
import { getAuthErrorMessage } from '../authService';

const { authStub } = vi.hoisted(() => ({ authStub: { currentUser: null } }));
vi.mock('../../lib/firebase', () => ({ auth: authStub }));
vi.mock('firebase/auth', () => ({
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  GoogleAuthProvider: class {
    addScope() {}
  },
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
  signOut: vi.fn(),
  updateProfile: vi.fn(),
  onAuthStateChanged: vi.fn(() => () => {}),
  applyActionCode: vi.fn(),
  checkActionCode: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));

describe('getAuthErrorMessage', () => {
  it('maps known Firebase auth error codes to friendly messages', () => {
    expect(getAuthErrorMessage({ code: 'auth/invalid-email' })).toContain('email address looks invalid');
    expect(getAuthErrorMessage({ code: 'auth/wrong-password' })).toContain('Incorrect password');
    expect(getAuthErrorMessage({ code: 'auth/email-already-in-use' })).toContain('already exists');
    expect(getAuthErrorMessage({ code: 'auth/popup-blocked' })).toContain('popup was blocked');
  });

  it('falls back to a generic message for unknown errors', () => {
    expect(getAuthErrorMessage({ code: 'auth/unknown-code' })).toContain('An unexpected error occurred');
  });

  it('handles non-object garbage', () => {
    expect(getAuthErrorMessage('boom')).toContain('An unexpected error occurred');
  });
});