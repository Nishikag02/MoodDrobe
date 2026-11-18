import path from "path"
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'

import tailwindcss from '@tailwindcss/vite'

import { defineConfig } from 'vite'

// The MoodDrobe ML service (FastAPI). Override with ML_SERVICE_URL if it runs elsewhere.
const ML_SERVICE_URL = process.env.ML_SERVICE_URL ?? 'http://127.0.0.1:8000'

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
    proxy: {
      // Browser calls /ml/... and Vite forwards it to FastAPI, so no CORS setup is needed.
      '/ml': { target: ML_SERVICE_URL, changeOrigin: true, rewrite: (p) => p.replace(/^\/ml/, '') },
    },
  },
  preview: {
    proxy: {
      '/ml': { target: ML_SERVICE_URL, changeOrigin: true, rewrite: (p) => p.replace(/^\/ml/, '') },
    },
  },
})
