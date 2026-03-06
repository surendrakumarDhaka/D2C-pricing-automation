import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort = Number(env.VITE_PORT || 5173)
  const basePath = env.VITE_BASE_PATH || '/'
  return {
    base: basePath,
    plugins: [react()],
    server: {
      port: devPort,
      host: true,
      proxy: {
        '/api': 'http://localhost:8001'
      }
    }
  }
})
