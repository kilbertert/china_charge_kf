import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  const backendPort = env.VITE_BACKEND_PORT || '8011'
  const basePath = env.VITE_BASE_PATH || '/'

  return {
    base: basePath,
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      cors: true,
      allowedHosts: true,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})
