import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Workspace installs can put React Flow at the root and React in frontend/.
  // Hooks and the renderer must share React's dispatcher, even in that layout.
  resolve: { dedupe: ['react', 'react-dom'] },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8000' } },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { rollupOptions: { output: { manualChunks: { network: ['@xyflow/react'], surface: ['three'] } } } },
});
