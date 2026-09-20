import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

// Firebase web configuration MUST come from the environment. No fallback
// constants are shipped: silently defaulting to a fixture project would make
// a misconfigured deploy look like it works while authenticating users
// against the wrong project (or, worse, leaking one project's API key into
// every bundle). Fail fast with an actionable message instead.
function requireFirebaseEnv(name: string): string {
  const value = (import.meta.env as Record<string, string | undefined>)[name];
  if (!value) {
    throw new Error(
      `[LegalLens] Missing required Firebase config "${name}". ` +
        'Copy .env.example to .env and fill in your Firebase web app values ' +
        '(Vite loads .env; Vercel needs the matching VITE_FIREBASE_* env vars).'
    );
  }
  return value;
}

const firebaseConfig = {
  apiKey: requireFirebaseEnv('VITE_FIREBASE_API_KEY'),
  authDomain: requireFirebaseEnv('VITE_FIREBASE_AUTH_DOMAIN'),
  projectId: requireFirebaseEnv('VITE_FIREBASE_PROJECT_ID'),
  storageBucket: requireFirebaseEnv('VITE_FIREBASE_STORAGE_BUCKET'),
  messagingSenderId: requireFirebaseEnv('VITE_FIREBASE_MESSAGING_SENDER_ID'),
  appId: requireFirebaseEnv('VITE_FIREBASE_APP_ID'),
};

// Initialize Firebase (singleton pattern)
const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();

export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);
export const googleProvider = new GoogleAuthProvider();

export default app;
