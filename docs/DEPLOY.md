# 生产部署指南（子路径部署）

本文档讲清 H5 前端在 **子路径部署**（如 `https://ai.trendpower.cc/chat/`）下的完整配置和发布流程。配合根目录的 `README.md` 使用。

---

## 1. 架构

```
[浏览器] → ai.trendpower.cc/chat/  ─┐
                                     ├─ 外层 nginx（已存在，配置略）
[浏览器] → ai.trendpower.cc/chat/api/chat ┘   ↓ 反代到 china-charge-backend-dify:8012
                                     ↓
                                  Dify 后端 (uvicorn, port 8012)
                                     ↓
                                  Dify Workflow + 知识库
```

**关键约束**：
- H5 不是部署在域根，而是子路径 `/chat/`（已有其他系统在根路径）
- API 路径必须和前端子路径对齐：`/chat/api/chat`
- OSS 图片 / 视频走的是第三方域名（CDN 或 OSS 公网域名），前端直接 `<img src>` 加载

---

## 2. 关键环境变量

`frontend/.env`（构建时 baked-in）：

| 变量 | 当前值 | 含义 |
|---|---|---|
| `VITE_API_BASE` | `/chat` | fetch 前缀。空 = 同源 `/api/chat`；子路径部署必须写 `/chat` |
| `VITE_BASE_PATH` | `/chat/` | Vite `base`，影响 index.html 里所有 asset 路径 |
| `VITE_BACKEND_PORT` | `8012` | dev 模式下 vite proxy 的目标端口（**不影响生产**） |

**改完 `.env` 必须重新 `npm run build`**，变量在构建时固化进 bundle。

---

## 3. nginx 侧配置（外层 nginx，不在仓库内）

外层 nginx 把两个前缀路由到对应后端：

```nginx
server {
  listen 443 ssl;
  server_name ai.trendpower.cc;

  # H5 静态资源
  location /chat/ {
    alias /www/wwwroot/ai.trendpower.cc/chat/;
    try_files $uri $uri/ /chat/index.html;   # SPA fallback
    expires 1h;                              # 短期缓存，方便新 bundle 生效
  }

  # Dify 后端 API（同子路径前缀保持一致）
  location /chat/api/ {
    proxy_pass http://127.0.0.1:8012/api/;   # 注意尾部斜杠：剥离 /chat 前缀
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 50m;                # 音频/图片上传需要
  }
}
```

**两个坑**：
1. `location /chat/` + `alias /www/wwwroot/.../chat/` — `alias` 末尾**必须**有 `/`，`location` 末尾也建议有 `/`，否则路径拼接会错位。
2. `proxy_pass http://127.0.0.1:8012/api/` — 末尾的 `/` 让 nginx 把 `/chat/api/chat` 改写成 `/api/chat` 再转发。如果写成 `http://127.0.0.1:8012/api`（无尾斜杠），会变成 `/api/chat/api/chat` → 404。

---

## 4. 发布流程

### 4.1 一键脚本（推荐）

```bash
# 在服务器上
cd /root/dify/china_charge_kf   # 或你部署仓库的实际路径
bash scripts/deploy.sh
```

脚本自动完成：
1. `npm ci` + `npm run build`
2. 备份当前 `/www/wwwroot/ai.trendpower.cc/chat/` 到 `chat.bak.<时间戳>`
3. 复制新 `dist/assets/*` 到部署目录
4. 验证新 bundle 含 `mediaBubble`（图片渲染代码）
5. 失败时自动回滚

### 4.2 手动步骤（出问题时用）

```bash
cd /root/dify/china_charge_kf/frontend

# 1. 备份
[ -d /www/wwwroot/ai.trendpower.cc/chat ] && \
  cp -a /www/wwwroot/ai.trendpower.cc/chat \
        /www/wwwroot/ai.trendpower.cc/chat.bak.$(date +%Y%m%d_%H%M%S)

# 2. 重新构建
npm ci
npm run build

# 3. 复制新产物
rm -f /www/wwwroot/ai.trendpower.cc/chat/assets/*.js \
      /www/wwwroot/ai.trendpower.cc/chat/assets/*.css
cp dist/assets/* /www/wwwroot/ai.trendpower.cc/chat/assets/
cp dist/index.html /www/wwwroot/ai.trendpower.cc/chat/index.html
[ -f dist/vite.svg ] && cp dist/vite.svg /www/wwwroot/ai.trendpower.cc/chat/vite.svg

# 4. 验证
grep -c mediaBubble /www/wwwroot/ai.trendpower.cc/chat/assets/*.js  # 应该 >= 1
curl -s http://ai.trendpower.cc/chat/api/health | head -c 200       # 应该返回 {"ok":true,...}
```

---

## 5. 排障速查

| 症状 | 根因 | 验证方法 |
|---|---|---|
| 控制台 `GET /assets/xxx.js 404` | `VITE_BASE_PATH` 没设或 build 没重跑 | `curl http://ai.trendpower.cc/chat/ \| grep assets` 路径前缀 |
| 控制台 `POST /api/chat 404` | `VITE_API_BASE` 留空 + 部署在子路径 | bundle 里搜 `Ht="/chat"` 是否 baked in |
| 助手气泡只显示文字，media=[] 在响应里 | 后端旧版本或知识库没图片 | `curl POST /chat/api/chat ...` 看响应 JSON |
| 助手气泡无图（media=有但前端没渲染） | 前端 bundle 没含 media 代码 | `grep -c mediaBubble <bundle>.js` 必须 ≥ 1 |
| 图片/视频 403 或 CORS 错误 | OSS Bucket 没配 CORS | 见 [docs/IMAGE_REPLY.md §CORS](./IMAGE_REPLY.md#cors-配置) |
| 部署后用户浏览器还是旧的 | 浏览器或 CDN 缓存 | 强制刷新 `Ctrl+Shift+R`；外层 nginx 加 `Cache-Control: no-cache` |

---

## 6. 备份管理

`scripts/deploy.sh` 自动保留最近 5 个备份：

```bash
ls /www/wwwroot/ai.trendpower.cc/chat.bak.*
# chat.bak.20260615_220630
# chat.bak.20260615_221015
# chat.bak.20260615_221430
# ...

# 手动回滚到指定版本
rm -rf /www/wwwroot/ai.trendpower.cc/chat
mv /www/wwwroot/ai.trendpower.cc/chat.bak.20260615_221430 \
   /www/wwwroot/ai.trendpower.cc/chat
```

---

## 7. Dify 后端部署

Dify 后端在生产用 docker-compose 启（**前端 nginx 必须能访问到**）：

```bash
cd /root/dify/china_charge_kf
docker compose up -d backend-dify
# 容器 china-charge-backend-dify-internal 监听容器内 8012
# 暴露到宿主 8012，由外层 nginx 转发到 8012
```

健康检查：

```bash
docker exec china-charge-backend-dify-internal \
  curl -f http://localhost:8012/api/health
# {"ok":true,"backend":"dify",...}
```

---

## 8. health_consult 模块（AI 健康咨询，端口 8013）

> 详见 [HEALTH_CONSULT.md](./HEALTH_CONSULT.md)。本节只讲生产部署相关的差异点。

### 8.1 启动容器

```bash
cd /root/dify/china_charge_kf
# docker-compose.yml 已含 backend-health-consult service
docker compose up -d backend-health-consult
# 容器 china-charge-backend-health-consult 监听 8013
```

环境变量从 `./backend/.env.dify-consult` 读,首次部署需从 example 复制:

```bash
cp backend/.env.dify-consult.example backend/.env.dify-consult
# 然后填 DIFY_API_KEY / DIFY_DATASET_*
```

### 8.2 nginx 路由

外层 nginx `ai.trendpower.cc.conf` 必须有这条 location(放在 `/chat/api/` 通配规则**之前**):

```nginx
location ^~ /chat/api/health-consult/ {
    proxy_pass http://127.0.0.1:8013/api/health-consult/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

`^~` 修饰符保证一旦匹配 `health-consult` 前缀,**不再走**通配的 `/chat/api/`,避免被劫持到 8012。

### 8.3 前端访问

`http://ai.trendpower.cc/chat/?view=health` 走 `HealthConsultApp`,其他走既有 chat。

### 8.4 健康检查

```bash
# 直接 (容器)
docker exec china-charge-backend-health-consult \
  curl -f http://localhost:8013/api/health-consult/health

# 通过 nginx (生产 URL)
curl -s http://ai.trendpower.cc/chat/api/health-consult/health
# {"status":"ok","service":"health-consult","version":"0.1.0"}
```
