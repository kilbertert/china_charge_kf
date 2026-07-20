from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

import httpx
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app_dify.config import settings
from app_dify.dify_client import (
    DifyClient,
    DifyError,
    SWITCH_TO_BUG,
    SWITCH_TO_KB_REENTRY,
    SWITCH_TO_KB_DONE,
    parse_switch_markers,
    strip_sys_markers,
)
from app_dify.response_parser import extract_assistant_text_and_media
from app_dify.schemas import ChatResponse, MediaItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("app_dify")

app = FastAPI(
    title="China Charge - Dify H5 Chat Backend",
    version="0.2.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _sniff_audio_type(filename: str, declared: str | None) -> str:
    """Normalize audio MIME type for Dify upload (Dify accepts wav/mp3/m4a/webm)."""
    name = (filename or "").lower()
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".mp3"):
        return "audio/mpeg"
    if name.endswith(".m4a"):
        return "audio/mp4"
    if name.endswith(".webm"):
        return "audio/webm"
    if name.endswith(".ogg") or name.endswith(".oga"):
        return "audio/ogg"
    if name.endswith(".mp4"):
        return "audio/mp4"
    return declared or "audio/wav"


# 前端 language 值 -> chatflow input_language select 接受的代码
# (app A/B 的 input_language 仅接受 ['zh','en','vi','th','ne',''])
_LANG_MAP = {
    "普通话": "zh", "中文": "zh", "zh": "zh", "chinese": "zh", "cn": "zh",
    "英文": "en", "英语": "en", "en": "en", "english": "en",
    "越南语": "vi", "vi": "vi", "vietnamese": "vi",
    "泰语": "th", "th": "th", "thai": "th",
}


def _normalize_language(raw: str) -> str:
    """把前端发的语言文案归一化为 chatflow input_language 代码; 无法识别返回 ''。"""
    s = (raw or "").strip()
    if not s:
        return ""
    return _LANG_MAP.get(s.lower(), "")


_MAX_IMAGE_BYTES = 10 * 1024 * 1024


class InvalidImageError(ValueError):
    """前端上传的图片为空、超限或不是 Dify vision 支持的真实图片。"""


def _detect_image_mime(content: bytes) -> str | None:
    """按魔数识别 Dify vision 支持的图片；不再用扩展名伪装未知内容。"""
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


# ----------------------------------------------------------------------
# ChatflowRouter: A/B 双 app marker 路由, 与 WeCom 机器人对齐
# ----------------------------------------------------------------------

class ChatflowRouter:
    """双 chatflow app 路由器。

    - app A (charge_charging_A_kbqa): KB 问答主入口
    - app B (charge_charging_B_bugtrack): bug 追踪
    - marker 驱动改投: SWITCH_TO_BUG(A->B) / KB_REENTRY(B->A) / KB_DONE(B->A 收尾)
    - 每 session 维持 {active, conv_a, conv_b} 多轮状态 (内存, 进程内)
    - 图片/音频在【发送点】按目标 app 上传, 根除跨 app file_id 失效
    """

    _MAX_ROUTES = 3  # 防 A<->B ping-pong 改投上限
    _SESSION_TTL = 1800  # 会话状态 TTL (秒); 超时未活动视为新会话, 对齐 wecom 30min

    def __init__(self, api_base: str, key_a: str, key_b: str, end_user: str) -> None:
        if not key_a:
            raise RuntimeError("DIFY_API_KEY_A (或旧 DIFY_API_KEY) 未配置")
        self._api_base = api_base
        self._end_user = end_user
        self._client_a = DifyClient(api_base, key_a, end_user)
        self._dual = bool(key_b)
        self._client_b = DifyClient(api_base, key_b, end_user) if self._dual else None
        self._store: dict[str, dict] = {}  # {sid: {"state": {...}, "ts": monotonic}}
        self._lock = asyncio.Lock()

    def _client_for(self, app: str) -> DifyClient:
        if self._dual and app == "B":
            return self._client_b  # type: ignore[return-value]
        return self._client_a

    async def _build_files(
        self,
        client: DifyClient,
        image_bytes: bytes | None,
        image_name: str | None,
        audio_bytes: bytes | None,
        audio_name: str | None,
    ) -> list[dict[str, Any]]:
        """在发送点把图片/音频上传到【目标 client 绑定的 app】并构造 files 数组。

        跨 app 改投时会用新 target client 再次调用本方法重新上传, 保证 file_id
        归属正确 (A 的 file_id 不能发给 B)。
        """
        files: list[dict[str, Any]] = []
        if image_bytes:
            ctype = _detect_image_mime(image_bytes)
            if not ctype:
                raise InvalidImageError("图片格式无效，仅支持 PNG/JPG/GIF/WEBP")
            fid = await client.upload_file(
                filename=image_name or "image.png",
                content=image_bytes,
                content_type=ctype,
            )
            files.append(DifyClient.file_ref(fid, "image"))
            app_name = "B" if client is self._client_b else "A"
            log.info(
                "[ROUTER] 图片上传至 app=%s file_id=%s size=%dB mime=%s",
                app_name, fid[:8], len(image_bytes), ctype,
            )
        if audio_bytes:
            ctype = _sniff_audio_type(audio_name or "", None)
            fid = await client.upload_file(
                filename=audio_name or "audio.wav",
                content=audio_bytes,
                content_type=ctype,
            )
            files.append(DifyClient.file_ref(fid, "audio"))
        return files

    async def _call(
        self,
        client: DifyClient,
        query: str,
        inputs: dict[str, Any],
        files: list[dict[str, Any]],
        conversation_id: str,
    ) -> dict[str, Any]:
        """调用 chatflow；带文件失败时必须显式报错，禁止静默丢图后伪装成功。"""
        return await client.run_chatflow(
            query=query, inputs=inputs, files=files or None,
            conversation_id=conversation_id,
        )

    async def _cache_bug_image(
        self,
        conversation_id: str,
        session_id: str,
        image_bytes: bytes,
        image_name: str | None,
    ) -> bool:
        """把 H5 原图缓存到 120 Bug API，供后续确认轮写入飞书附件。"""
        base = settings.bugtrack_api_base.rstrip("/")
        if not base:
            return True
        ctype = _detect_image_mime(image_bytes)
        if not conversation_id or not ctype:
            return False
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.bugtrack_image_cache_timeout)
            ) as client:
                response = await client.post(
                    f"{base}/internal/bugtrack/cache-image",
                    data={
                        "conversation_id": conversation_id,
                        "session_id": session_id,
                        "channel": "h5",
                        "user_key": session_id,
                    },
                    files={
                        "image": (
                            image_name or "bug-screenshot.jpg",
                            image_bytes,
                            ctype,
                        )
                    },
                )
            if response.status_code >= 400:
                log.warning(
                    "[ROUTER] Bug 截图缓存失败 conv=%s HTTP=%d",
                    conversation_id[:8], response.status_code,
                )
                return False
            body = response.json()
            if not body.get("success"):
                log.warning("[ROUTER] Bug 截图缓存返回失败 conv=%s", conversation_id[:8])
                return False
            log.info(
                "[ROUTER] Bug 截图已跨轮缓存 conv=%s size=%dB",
                conversation_id[:8], len(image_bytes),
            )
            return True
        except (httpx.HTTPError, ValueError) as exc:
            log.warning(
                "[ROUTER] Bug 截图缓存异常 conv=%s error=%s",
                conversation_id[:8], str(exc)[:120],
            )
            return False

    async def _load_route_state(self, session_id: str) -> dict[str, str] | None:
        """Restore A/B Dify conversation ids after an H5 process restart."""
        base = settings.bugtrack_api_base.rstrip("/")
        if not base:
            return None
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.bugtrack_image_cache_timeout)
            ) as client:
                response = await client.get(
                    f"{base}/internal/bugtrack/route-session/h5/{session_id}"
                )
            response.raise_for_status()
            route = (response.json() or {}).get("route")
            if not isinstance(route, dict):
                return None
            active = "B" if route.get("active") == "B" else "A"
            return {
                "active": active,
                "conv_a": str(route.get("conv_a") or ""),
                "conv_b": str(route.get("conv_b") or ""),
            }
        except (httpx.HTTPError, ValueError) as exc:
            log.warning(
                "[ROUTER] 远端路由状态读取失败 session=%s error=%s",
                session_id[:12], str(exc)[:120],
            )
            return None

    async def _save_route_state(self, session_id: str, state: dict[str, Any]) -> bool:
        """Persist only routing identifiers; message/business state stays in Bug DB/Dify."""
        base = settings.bugtrack_api_base.rstrip("/")
        if not base:
            return True
        payload = {
            "active": "B" if state.get("active") == "B" else "A",
            "conv_a": str(state.get("conv_a") or ""),
            "conv_b": str(state.get("conv_b") or ""),
            "route_data": {},
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.bugtrack_image_cache_timeout)
            ) as client:
                response = await client.put(
                    f"{base}/internal/bugtrack/route-session/h5/{session_id}",
                    json=payload,
                )
            response.raise_for_status()
            return bool((response.json() or {}).get("success"))
        except (httpx.HTTPError, ValueError) as exc:
            log.warning(
                "[ROUTER] 远端路由状态保存失败 session=%s error=%s",
                session_id[:12], str(exc)[:120],
            )
            return False

    async def chat(
        self,
        *,
        session_id: str,
        text: str,
        image_bytes: bytes | None = None,
        image_name: str | None = None,
        audio_bytes: bytes | None = None,
        audio_name: str | None = None,
        language: str = "",
    ) -> dict[str, Any]:
        query = (text or "").strip() or "收到您的消息"
        inputs: dict[str, Any] = {}
        lang = (language or "").strip()
        if lang:
            inputs["input_language"] = lang

        async with self._lock:
            entry = self._store.get(session_id)
            now = time.monotonic()
            # 超时未活动 -> 视为新会话: 重置 active/conv, 避免陈旧 conv_id 误用
            if entry and (now - entry.get("ts", 0.0)) > self._SESSION_TTL:
                entry = None
            state = dict((entry or {}).get("state") or {})

        if not state:
            state = await self._load_route_state(session_id) or {
                "active": "A", "conv_a": "", "conv_b": ""
            }

        active = state.get("active", "A")
        client = self._client_for(active)
        conv_id = (state.get("conv_a") if active == "A" else state.get("conv_b")) or ""
        files = await self._build_files(client, image_bytes, image_name, audio_bytes, audio_name)
        bug_image_cached = False

        # 已在 B 会话中时，必须先把本轮图片绑定草稿，再让 Dify 处理“确认写表”。
        # 否则确认轮上传的图片会在 /add 完成后才到 120，漏出本次飞书记录。
        if image_bytes and active == "B" and conv_id:
            bug_image_cached = await self._cache_bug_image(
                conv_id, session_id, image_bytes, image_name
            )
            if not bug_image_cached:
                raise DifyError("Bug screenshot persistence failed before chatflow")

        raw = await self._call(client, query, inputs, files, conv_id)
        answer = (raw or {}).get("answer") or ""
        new_conv = (raw or {}).get("conversation_id") or ""
        if new_conv:
            state["conv_a" if active == "A" else "conv_b"] = new_conv

        # 双 app marker 驱动改投循环
        if self._dual:
            for _ in range(self._MAX_ROUTES):
                answer, switches = parse_switch_markers(answer)
                re_route: Optional[str] = None
                if SWITCH_TO_BUG in switches and active == "A":
                    state["active"] = "B"
                    re_route = "B"
                elif SWITCH_TO_KB_REENTRY in switches and active == "B":
                    state["active"] = "A"
                    re_route = "A"
                elif SWITCH_TO_KB_DONE in switches and active == "B":
                    state["active"] = "A"  # 发 B 话术, 下条->A, 不改投
                if not re_route:
                    break
                target = self._client_for(re_route)
                tconv = (state.get("conv_b") if re_route == "B" else state.get("conv_a")) or ""
                tfiles = await self._build_files(target, image_bytes, image_name, audio_bytes, audio_name)
                if image_bytes and re_route == "B" and tconv and not bug_image_cached:
                    bug_image_cached = await self._cache_bug_image(
                        tconv, session_id, image_bytes, image_name
                    )
                    if not bug_image_cached:
                        raise DifyError(
                            "Bug screenshot persistence failed before rerouted chatflow"
                        )
                raw2 = await self._call(target, query, inputs, tfiles, tconv)
                answer = (raw2 or {}).get("answer") or ""
                nc2 = (raw2 or {}).get("conversation_id") or ""
                if nc2:
                    state["conv_b" if re_route == "B" else "conv_a"] = nc2
                active = state.get("active", "A")
                new_conv = nc2 or new_conv

        if image_bytes and state.get("active") == "B" and not bug_image_cached:
            bug_conv = (state.get("conv_b") or "").strip()
            cached = await self._cache_bug_image(
                bug_conv, session_id, image_bytes, image_name
            )
            if not cached:
                answer = (
                    answer.rstrip()
                    + "\n\n截图暂未保存成功，请重新上传一次后再确认记录。"
                )

        # 剥离所有 <!--SYS:...--> 控制标记 (SWITCH 残留 + TIMER 等 WeCom 协议标记)。
        # H5 不作用于这些协议标记, 统一从用户可见文本移除。
        answer = strip_sys_markers(answer)

        async with self._lock:
            self._store[session_id] = {"state": state, "ts": time.monotonic()}
            # lazy 清理过期项, 防长期累积 (阈值触发扫描, 避免每次请求开销)
            if len(self._store) > 512:
                cutoff = time.monotonic() - self._SESSION_TTL
                for k in [k for k, v in self._store.items() if v.get("ts", 0.0) <= cutoff]:
                    self._store.pop(k, None)

        await self._save_route_state(session_id, state)

        log.info(
            "[ROUTER] session=%s active=%s conv_a=%s conv_b=%s answer_len=%d",
            session_id[:12], state.get("active"), (state.get("conv_a") or "")[:8],
            (state.get("conv_b") or "")[:8], len(answer),
        )

        # 归一化为 workflow 形态, 复用 response_parser 抽取 text + media
        normalized_raw = {
            "data": {"outputs": {"output": answer, "answer": answer}},
            "conversation_id": new_conv,
        }
        return {"assistant_text": answer, "raw": normalized_raw, "conversation_id": new_conv}


router = ChatflowRouter(
    api_base=settings.dify_api_base,
    key_a=settings.api_key_a,
    key_b=settings.dify_api_key_b,
    end_user=settings.dify_end_user,
)


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "backend": "dify-chatflow",
        "api_base": settings.dify_api_base,
        "end_user": settings.dify_end_user,
        "dual_app": router._dual,
        "bugtrack_image_cache": bool(settings.bugtrack_api_base),
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    text: str = Form(""),
    image: Optional[UploadFile] = File(default=None),
    audio: Optional[UploadFile] = File(default=None),
    language: str = Form("中文"),
    session_id: Optional[str] = Form(default=None),
) -> ChatResponse:
    # session_id: 前端 localStorage 持久化; 首次不传则后端生成并回传
    sid = (session_id or "").strip() or f"h5-{uuid.uuid4().hex}"

    image_bytes: bytes | None = None
    image_name: str | None = None
    if image is not None:
        content = await image.read(_MAX_IMAGE_BYTES + 1)
        if not content:
            return JSONResponse(
                status_code=400,
                content={"detail": "上传的图片为空，请重新选择图片", "session_id": sid},
            )
        if len(content) > _MAX_IMAGE_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "图片超过 10MB，请压缩后重试", "session_id": sid},
            )
        if not _detect_image_mime(content):
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "图片格式无效，仅支持 PNG、JPG、GIF、WEBP",
                    "session_id": sid,
                },
            )
        image_bytes = content
        image_name = image.filename or "image"

    audio_bytes: bytes | None = None
    audio_name: str | None = None
    if audio is not None:
        content = await audio.read()
        if content:
            audio_bytes = content
            audio_name = audio.filename or "audio.wav"

    try:
        result = await router.chat(
            session_id=sid,
            text=text,
            image_bytes=image_bytes,
            image_name=image_name,
            audio_bytes=audio_bytes,
            audio_name=audio_name,
            language=_normalize_language(language),
        )
    except InvalidImageError as e:
        return JSONResponse(
            status_code=400,
            content={"detail": str(e), "session_id": sid},
        )
    except DifyError as e:
        log.error("Chatflow error: %s", e)
        detail = (
            "图片处理失败，请确认图片清晰且格式受支持后重试"
            if image_bytes
            else "AI 服务暂时不可用，请稍后重试"
        )
        return JSONResponse(
            status_code=502,
            content={"detail": detail, "session_id": sid},
        )

    assistant_text, media = extract_assistant_text_and_media(
        result["raw"], preferred_key="output"
    )
    return ChatResponse(
        assistant_text=assistant_text,
        image_id=None,
        audio_id=None,
        media=[MediaItem(**m) for m in media],
        raw=result["raw"],
        session_id=sid,
    )
