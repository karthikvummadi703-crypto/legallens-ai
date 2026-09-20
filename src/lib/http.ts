import { auth } from './firebase';

/**
 * Shared HTTP client for the LegalLens backend API.
 *
 * Centralises the API base URL (VITE_API_BASE_URL) and Firebase ID-token
 * attachment so no service file duplicates them. `apiFetch` behaves exactly
 * like `fetch`, but resolves the /api base URL and attaches the current
 * user's Firebase ID token as a Bearer Authorization header. Network errors
 * and non-2xx responses are NOT swallowed here — callers keep their own
 * `res.ok` handling, exactly as before.
 *
 * When no user is signed in, requests are sent without an Authorization
 * header (the backend's dev-mode may still accept them locally).
 */
const _rawBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export const API_BASE_URL = _rawBase + '/api';

async function getIdTokenSilently(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  try {
    return await user.getIdToken();
  } catch {
    // Token fetch failures (offline dev, expired session) yield an
    // unauthenticated request; the backend rejects it with 401/403.
    return null;
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = await getIdTokenSilently();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}