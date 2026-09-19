import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyBCmJ5uW6i19EzrNTXcr4D4SYkafKAxXI4",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "my-project-495811.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "my-project-495811",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "my-project-495811.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "63244814075",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:63244814075:web:2d1aa1a483c3156f21925e"
};

// Initialize Firebase (singleton pattern)
const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();

export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);
export const googleProvider = new GoogleAuthProvider();

export default app;
