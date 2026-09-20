import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Provide every Firebase env var so module-level Firebase config in
// src/lib/firebase.ts never throws during tests. Real auth is not used;
// service tests may import { auth } and stub currentUser directly.
vi.stubEnv('VITE_FIREBASE_API_KEY', 'test-api-key');
vi.stubEnv('VITE_FIREBASE_AUTH_DOMAIN', 'test.firebaseapp.com');
vi.stubEnv('VITE_FIREBASE_PROJECT_ID', 'test-project');
vi.stubEnv('VITE_FIREBASE_STORAGE_BUCKET', 'test.appspot.com');
vi.stubEnv('VITE_FIREBASE_MESSAGING_SENDER_ID', '1234567890');
vi.stubEnv('VITE_FIREBASE_APP_ID', '1:123:web:test');
vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');

// --- jsdom polyfills the app touches that jsdom does not implement -------

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
}

if (typeof globalThis.matchMedia === 'undefined') {
  (globalThis as unknown as { matchMedia: unknown }).matchMedia = () => ({
    matches: false,
    media: '',
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});