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
  // 生产构建后的本地预览（npm run preview）：同样代理 /api，模拟部署环境
  preview: {
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
