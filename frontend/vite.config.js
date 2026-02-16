import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort = Number(env.VITE_PORT || 5173)
  return {
    plugins: [react()],
    server: {
      port: devPort,
      host: true,
      proxy: {
        '/api': 'http://localhost:8000'
      }
    }
  }
})
