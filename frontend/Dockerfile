FROM node:24-alpine AS build

# build context 为项目根: COPY frontend/ + shared/
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN npm ci
COPY frontend/ /app/frontend/

# 健康合规单一事实源 (prebuild gen 脚本从 /app/shared/compliance.yaml 生成 ts)
COPY shared/ /app/shared/

# 构建期注入 Vite 构建变量 (dockerignore 已排除 .env.*, 这里用 ARG 重新生成 .env.production)
# 避免 .env.production 未进上下文时 base 默认 '/' 导致子路径部署 asset 404
ARG VITE_BASE_PATH=/
ARG VITE_API_BASE=
ARG VITE_BACKEND_PORT=8012
RUN printf 'VITE_BASE_PATH=%s\nVITE_API_BASE=%s\nVITE_BACKEND_PORT=%s\n' \
      "$VITE_BASE_PATH" "$VITE_API_BASE" "$VITE_BACKEND_PORT" > .env.production

RUN npm run build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
