import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api 请求代理到后端 FastAPI（8000），前端无需关心跨域
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
