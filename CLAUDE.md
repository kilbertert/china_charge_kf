# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

H5 智能客服 - a browser-based customer service chat application (text/image/voice input) for 充电桩 (charging pile) customer service. Powered by a FastAPI backend that calls **Dify chatflow** apps with **A/B dual-app marker routing** (aligned with the WeCom bot).

Also contains a separate 健康咨询 (health consult) module (`backend/health_consult/`, port 8013) and a charge-consult module (`backend/charge_consult/`, port 8014).

**Stack**: React + TypeScript + Vite (frontend) | FastAPI (backend) | Dify chatflow A/B | Nginx (proxy) | Docker Compose (single deployment)

## Dev Commands

### Frontend
```bash
cd frontend
npm run dev          # Vite dev server with HMR (VITE_API_BASE empty -> /api proxy)
npm run build         # TS build + Vite production bundle
npm run lint          # ESLint check
```

### Backend (H5 charge chat - Dify chatflow A/B)
```bash
cd backend
uvicorn app_dify.main:app --host 0.0.0.0 --port 8012 --reload   # local dev server
# 本地调试需在 backend/.env (config.py env_file=".env") 填 DIFY_API_KEY_A/B + DIFY_API_BASE
```
Health check: `curl http://localhost:8012/api/health` -> `{"ok":true,"backend":"dify-chatflow","dual_app":true,...}`

### Docker (production, single compose)
```bash
cd /root/dify/china_charge_kf        # on prod host 124
docker compose build backend-dify frontend
docker compose up -d --no-deps backend-dify frontend
```

## Architecture

```
Browser (H5 at https://ai.trendpower.cc/chat/)
  └── 宿主 Nginx (443) ── /chat/ ──────── china-charge-frontend (8082, nginx+dist)
                       └─ /chat/api/ ──── china-charge-backend-dify (127.0.0.1:8012)
                                            └── ChatflowRouter
                                                  ├─ app A (charge_charging_A_kbqa)  -> Dify /chat-messages
                                                  └─ app B (charge_charging_B_bugtrack) -> Dify /chat-messages
                                                                       (Dify api:5001 via docker_default network)
```

- **Frontend** (`frontend/src/App.tsx`): single-page chat UI; text/voice/image input; POSTs multipart/form-data to `${VITE_API_BASE}/api/chat`; carries `session_id` (localStorage持久化) for multi-turn; zh/en/vi i18n
- **Backend** (`backend/app_dify/main.py`): FastAPI; `POST /api/chat` receives `text`, optional `image`/`audio`, `language`, optional `session_id`; calls `ChatflowRouter.chat()`; returns `ChatResponse{assistant_text, media, session_id, ...}`
- **ChatflowRouter** (`backend/app_dify/main.py`): dual DifyClient (A/B) + per-session in-memory state `{active, conv_a, conv_b}` + marker-driven re-route loop (max 3). Image/audio uploaded at **send-site** to the target app (root-cause fix for cross-app file_id invalidity)
- **DifyClient** (`backend/app_dify/dify_client.py`): `run_chatflow()` -> `POST /chat-messages {query, inputs, files, conversation_id, user}`; `upload_file()`; `parse_switch_markers()` + `strip_sys_markers()`
- **Markers** (`backend/app_dify/dify_client.py`): `<!--SYS:SWITCH_TO_BUG-->` (A->B), `<!--SYS:SWITCH_TO_KB_REENTRY-->` (B->A), `<!--SYS:SWITCH_TO_KB_DONE-->` (B->A收尾), `<!--SYS:TIMER|...-->` (WeCom timer, H5 strips). `strip_sys_markers()` removes all `<!--SYS:...-->` from user-facing text
- **Config** (`backend/app_dify/config.py`): Pydantic `Settings`, `env_file=".env"` (container relies on compose env_file -> env vars)
- **Response parsing** (`backend/app_dify/response_parser.py`): `extract_assistant_text_and_media()` extracts text + media URLs (regex fallback); `<think>` blocks stripped

## Production Deployment (124.243.178.156) — 单一 docker-compose

**Single source of truth**: `/root/dify/china_charge_kf/docker-compose.yml` manages the H5 app. Dify itself is a separate compose at `/root/dify/docker/docker-compose.yaml`.

| service | container | port | env_file | role |
|---|---|---|---|---|
| `backend-dify` | china-charge-backend-dify | 127.0.0.1:8012 | `./backend/.env.dify` | H5 charge chat backend (Dify chatflow A/B) |
| `frontend` | china-charge-frontend | 0.0.0.0:8082 | (build-time `.env.production`) | H5 static frontend |
| `backend-health-consult` | china-charge-backend-health-consult | 8013 | `.env.dify-consult` | health consult module |
| `backend-charge-consult` | china-charge-backend-charge-consult | 8014 | `.env.dify-charge` | charge consult module |
| `backend` (Coze) | china-charge-backend | 8011 | `./backend/.env` | **legacy, stopped** (Coze, broken) |

**Network**: `backend-dify` joins external `docker_default` (Dify's network) to reach `api:5001` by name. `DIFY_API_BASE=http://api:5001/v1`.

**宿主 Nginx vhost** (`/www/server/panel/vhost/nginx/ai.trendpower.cc.conf`):
- `/chat/api/health-consult/` -> `127.0.0.1:8013`
- `/chat/api/` -> `127.0.0.1:8012` (backend-dify)
- `/chat/` -> `127.0.0.1:8082` (frontend)

**Rebuild after code change**:
```bash
cd /root/dify/china_charge_kf
docker compose build backend-dify && docker compose up -d --no-deps --force-recreate backend-dify
# frontend: docker compose build frontend && docker compose up -d --no-deps --force-recreate frontend
```
(Use `--no-deps` for frontend to skip the legacy Coze `backend` dependency; `frontend` now `depends_on: backend-dify`.)

⚠️ **历史教训**: 曾有宿主级 uvicorn (conda env `dify`, `--reload`, 读 `backend/.env`) 与 docker 容器并存，nginx 实际用宿主 uvicorn。**已下线**。现在 prod 后端唯一是 docker `backend-dify` (读 `.env.dify`)。改 prod 配置改 `.env.dify` + 重建容器，不要起宿主 uvicorn。

## Environment Variables

### Backend (`backend/.env.dify` — H5 charge chat, single source)
| Variable | Description | Default |
|---|---|---|
| `DIFY_API_BASE` | Dify API base (container 内 `http://api:5001/v1`) | `http://api:5001/v1` |
| `DIFY_API_KEY_A` | app A (charge_charging_A_kbqa) token | **required** |
| `DIFY_API_KEY_B` | app B (charge_charging_B_bugtrack) token; empty = single-app mode | `""` |
| `DIFY_END_USER` | Dify end_user (H5 共用, 按 conversation_id 隔离会话) | `h5-frontend-user` |
| `APP_CORS_ORIGINS` | CORS origins | `http://localhost:5173,...` |
| `PORT` | backend port | `8012` |

### Frontend (`frontend/.env.production` — build-time)
| Variable | Description |
|---|---|
| `VITE_BASE_PATH` | Vite base (sub-path deploy) = `/chat/` |
| `VITE_API_BASE` | API prefix = `/chat` (same-origin via nginx) |

## Key Implementation Notes

- **session_id multi-turn**: frontend generates/stores `session_id` in localStorage; backend tracks `{active, conv_a, conv_b}` per session_id (in-memory). First request without session_id -> backend generates `h5-<hex>` and returns it.
- **A/B marker routing**: app A detects bug intent -> emits `SWITCH_TO_BUG` -> backend re-routes same message to app B. `KB_REENTRY`/`KB_DONE` route B->A. Max 3 re-routes (anti ping-pong). All `<!--SYS:...-->` stripped from final reply.
- **Image at send-site**: image bytes carried app-agnostic in `input_data`; uploaded to the TARGET app's DifyClient right before `/chat-messages`. On re-route (A->B), re-uploaded to B. Root-cause fix for "A's file_id sent to B -> Invalid upload file".
- **Language normalize**: frontend sends `普通话`/`英文`/`越南语`; chatflow `input_language` only accepts `['zh','en','vi','th','ne','']`; `_normalize_language()` maps.
- **Audio**: recorded WebM/MP4 via `MediaRecorder`, uploaded as file (type `audio`); if app rejects (400), `_call()` retries without files.
- **Coze backend** (`backend/app/`, port 8011) is **legacy/stopped**; H5 migrated to Dify. `backend/.env` is the Coze service's env_file (currently misconfigured with Dify vars — do not use as app_dify config source).
- The "拍摄" (camera) button in `App.tsx` is visible but non-functional; image input comes from the file `<input capture="environment">` triggered by the "拍照/图片" panel button.
