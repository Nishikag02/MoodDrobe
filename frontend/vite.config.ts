import path from "path"
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'

import tailwindcss from '@tailwindcss/vite'

import { defineConfig } from 'vite'

// The MoodDrobe ML service (FastAPI). Override with ML_SERVICE_URL if it runs elsewhere.
const ML_SERVICE_URL = process.env.ML_SERVICE_URL ?? 'http://127.0.0.1:8000'
// Express backend (login, saved items, history).
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://127.0.0.1:3000'

const proxy = {
  // Browser calls /ml/... and Vite forwards it to FastAPI, so no CORS setup is needed.
  '/ml': { target: ML_SERVICE_URL, changeOrigin: true, rewrite: (p: string) => p.replace(/^\/ml/, '') },
  // Login, saved items and history live on Express. Keep the Origin header (no changeOrigin).
  '/api': { target: BACKEND_URL },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    babel({ presets: [reactCompilerPreset()] })
  ],
   resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // Public demo URL via a Cloudflare quick tunnel.
    allowedHosts: ['.trycloudflare.com'],
    proxy,
  },
  preview: {
    allowedHosts: ['.trycloudflare.com'],
    proxy,
  },
})
