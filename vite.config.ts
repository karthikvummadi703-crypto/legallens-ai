import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modify—file watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Ignore backend/ writes (db.json, uploads/) so they never trigger a
      // full-page reload — otherwise every chat message or upload reloads the app.
      watch: process.env.DISABLE_HMR === 'true' ? null : {
        ignored: ['**/backend/**', '**/node_modules/**', '**/.git/**'],
      },
    },
  };
});
