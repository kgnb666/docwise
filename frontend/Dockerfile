# DocWise 前端镜像（生产）：两阶段构建
#   阶段 1：Node 构建静态资源 → 阶段 2：nginx 服务 + /api 反代后端
# 本地开发请用 npm run dev（Vite 代理），不需要此镜像

# ---- 构建阶段 ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com
COPY . .
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
