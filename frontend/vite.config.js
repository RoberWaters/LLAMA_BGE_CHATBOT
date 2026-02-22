import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  define: {
    // Usado para cache-busting del AudioWorklet processor
    __APP_VERSION__: JSON.stringify(Date.now().toString()),
  },
  optimizeDeps: {
    include: ['simli-client']
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
