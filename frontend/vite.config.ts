import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // React y las gráficas van en archivos aparte: se cachean entre despliegues y las gráficas
        // solo se descargan al abrir Dashboard o Awareness.
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return 'vendor-react'
          if (/node_modules\/(recharts|d3-[^/]+|victory-vendor|react-smooth|recharts-scale|react-transition-group|eventemitter3|decimal\.js-light|fast-equals|tiny-invariant|lodash)\//.test(id)) return 'vendor-charts'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    proxy: { '/api': { target: process.env.VITE_API_PROXY || 'http://localhost:8000', changeOrigin: true } },
  },
})
