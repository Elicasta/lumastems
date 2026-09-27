import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'ui',
  plugins: [react()],
  clearScreen: false,
  build: {
    outDir: '../ui-dist',
    emptyOutDir: true
  },
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      ignored: ['**/src-tauri/**', '**/python-dist/**']
    }
  }
});
