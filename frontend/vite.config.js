import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 127.0.0.1, not "localhost": the backend binds IPv4 loopback only and
      // "localhost" may resolve to ::1 first.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws':  { target: 'ws://127.0.0.1:8000', ws: true, changeOrigin: true },
    },
  },
});
