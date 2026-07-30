from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any, Optional

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app_dify.bug_orchestrator_client import (
    BugOrchestratorClient,
    BugOrchestratorError,
)
from app_dify.config import settings
from app_dify.charge_reply_policy import get_charge_reply_policy
from app_dify.customer_intent import action, classify_customer_intent
from app_dify.dify_client import (
    DifyClient,
    DifyError,
    SWITCH_TO_BUG,
    parse_switch_markers,
    strip_sys_markers,
)
from app_dify.response_parser import extract_assistant_text_and_media
from app_dify.schemas import (
    ActionItem,
    ChatResponse,
    IntentPayload,
    MediaItem,
    NotificationAckRequest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("app_dify")

_H5_SESSION_ID_RE = re.compile(r"^h5-[0-9a-f]{32}$")

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


def _notification_session(
    authorization: str = Header(default="", alias="Authorization"),
) -> str:
    scheme, separator, token = (authorization or "").partition(" ")
    session_id = token.strip()
    if (
        not separator
        or scheme.lower() != "bearer"
        or not _H5_SESSION_ID_RE.fullmatch(session_id)
    ):
        raise HTTPException(status_code=401, detail="valid H5 session bearer required")
    return session_id


# 前端 language 值 -> chatflow input_language select 接受的代码
# (app A/B 的 input_language 仅接受 ['zh','en','vi','th','ne',''])
_LANG_MAP = {
    "普通话": "zh",
    "中文": "zh",
    "zh": "zh",
    "chinese": "zh",
    "cn": "zh",
    "英文": "en",
    "英语": "en",
    "en": "en",
    "english": "en",
    "越南语": "vi",
    "vi": "vi",
    "vietnamese": "vi",
    "泰语": "th",
    "th": "th",
    "thai": "th",
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
# ChatflowRouter: A chatflow + Bug 编排服务
# ----------------------------------------------------------------------


class ChatflowRouter:
    """A chatflow 与 Bug 编排服务的单入口路由器。

    - app A (charge_charging_A_kbqa): KB 问答主入口
    - Bug 意图直接调用 120 编排服务，不再通过 Dify B 收集或改投
    - route-session 保留 conv_b 字段仅用于历史兼容，运行时永远使用 A
    - 图片/音频仅在发送到 A 时上传；Bug 图片由编排服务持久化
    """

    _SESSION_TTL = 1800  # 会话状态 TTL (秒); 超时未活动视为新会话, 对齐 wecom 30min

    def __init__(self, api_base: str, key_a: str, end_user: str) -> None:
        if not key_a:
            raise RuntimeError("DIFY_API_KEY_A (或旧 DIFY_API_KEY) 未配置")
        self._api_base = api_base
        self._end_user = end_user
        self._client_a = DifyClient(api_base, key_a, end_user)
        self._store: dict[str, dict] = {}  # {sid: {"state": {...}, "ts": monotonic}}
        self._lock = asyncio.Lock()
        self._reply_policy = get_charge_reply_policy()
        self._bug_orchestrator = BugOrchestratorClient(
            settings.bugtrack_api_base,
            timeout=settings.bugtrack_orchestrator_timeout,
        )

    def _bug_v2_enabled(self) -> bool:
        return (
            settings.bugtrack_orchestrator_mode.strip().lower() == "active"
            and self._bug_orchestrator.enabled
        )

    async def _run_bug_v2(
        self,
        *,
        session_id: str,
        query: str,
        language: str,
        message_id: str,
        image_bytes: bytes | None,
        image_name: str | None,
        event: str = "",
    ) -> dict[str, Any]:
        image_mime = ""
        if image_bytes:
            image_mime = _detect_image_mime(image_bytes) or ""
            if not image_mime:
                raise InvalidImageError("图片格式无效，仅支持 PNG/JPG/GIF/WEBP")
        return await self._bug_orchestrator.message(
            text=query,
            session_id=session_id,
            language=language,
            message_id=message_id,
            image_bytes=image_bytes,
            image_name=image_name or "",
            image_mime=image_mime,
            event=event,
        )

    async def _remember_state(self, session_id: str, state: dict[str, Any]) -> None:
        async with self._lock:
            self._store[session_id] = {
                "state": dict(state),
                "ts": time.monotonic(),
            }
        await self._save_route_state(session_id, state)

    async def _finish_bug_v2(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        state["active"] = "A"
        is_suspended = str(result.get("state") or "") == "suspended"
        state["bug_v2_active"] = bool(result.get("continue_session")) and not is_suspended
        state["bug_v2_suspended"] = is_suspended
        state["vague_count"] = 0
        state["vague_exhausted"] = False
        await self._remember_state(session_id, state)
        answer = str(result.get("assistant_text") or "")
        conversation_id = str(state.get("conv_a") or "")
        normalized_raw = {
            "data": {
                "outputs": {
                    "output": answer,
                    "answer": answer,
                    "bug_v2": result,
                }
            },
            "conversation_id": conversation_id,
        }
        return {
            "assistant_text": answer,
            "raw": normalized_raw,
            "conversation_id": conversation_id,
            "intent": result.get("intent") or {
                "intent": "bug_report",
                "confidence": 1.0,
                "entities": {},
                "reason": "bug_state_machine",
            },
            "actions": result.get("actions") or [],
        }

    async def _bug_v2_retry_response(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        language: str,
        keep_session: bool,
        audio_unsupported: bool = False,
    ) -> dict[str, Any]:
        state["active"] = "A"
        state["bug_v2_active"] = keep_session
        state["bug_v2_suspended"] = False
        state["vague_count"] = 0
        state["vague_exhausted"] = False
        await self._remember_state(session_id, state)
        if audio_unsupported:
            messages = {
                "en": "Please continue this Bug report with text or an image.",
                "vi": "Vui lòng tiếp tục báo lỗi bằng văn bản hoặc hình ảnh.",
                "zh": "当前 Bug 提交流暂不支持语音续填，请改用文字或图片继续。",
            }
        else:
            messages = {
                "en": "The Bug service is temporarily unavailable. Please retry this message.",
                "vi": "Dịch vụ báo lỗi tạm thời không khả dụng. Vui lòng thử lại tin nhắn này.",
                "zh": "Bug 提交服务暂时不可用，本次消息尚未处理，请稍后重试。",
            }
        answer = messages.get(language, messages["zh"])
        payload = {
            "success": False,
            "assistant_text": answer,
            "state": "retry_required",
            "continue_session": keep_session,
            "fallback_required": False,
        }
        conversation_id = str(state.get("conv_a") or "")
        normalized_raw = {
            "data": {
                "outputs": {
                    "output": answer,
                    "answer": answer,
                    "bug_v2": payload,
                }
            },
            "conversation_id": conversation_id,
            "intent": {
                "intent": "bug_report",
                "confidence": 1.0,
                "entities": {},
                "reason": "bug_retry",
            },
            "actions": [],
        }
        return {
            "assistant_text": answer,
            "raw": normalized_raw,
            "conversation_id": conversation_id,
        }

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
            log.info(
                "[ROUTER] 图片上传至 app=A file_id=%s size=%dB mime=%s",
                fid[:8],
                len(image_bytes),
                ctype,
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
            query=query,
            inputs=inputs,
            files=files or None,
            conversation_id=conversation_id,
        )

    async def _load_route_state(self, session_id: str) -> dict[str, Any] | None:
        """Restore A conversation state; ignore historical B routing fields."""
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
            route_data = route.get("route_data")
            if route_data is None:
                route_data = {
                    key: value
                    for key, value in route.items()
                    if key not in {"active", "conv_a", "conv_b"}
                }
            if isinstance(route_data, str):
                try:
                    route_data = json.loads(route_data)
                except ValueError:
                    route_data = {}
            if not isinstance(route_data, dict):
                route_data = {}
            try:
                vague_count = max(0, int(route_data.get("vague_count") or 0))
            except (TypeError, ValueError):
                vague_count = 0
            return {
                "active": "A",
                "conv_a": str(route.get("conv_a") or ""),
                # Historical conv_b is deliberately ignored by the M4 runtime.
                "conv_b": "",
                "vague_count": vague_count,
                "vague_exhausted": bool(route_data.get("vague_exhausted")),
                "bug_v2_active": bool(route_data.get("bug_v2_active")),
                "bug_v2_suspended": bool(route_data.get("bug_v2_suspended")),
            }
        except (httpx.HTTPError, ValueError) as exc:
            log.warning(
                "[ROUTER] 远端路由状态读取失败 session=%s error=%s",
                session_id[:12],
                str(exc)[:120],
            )
            return None

    async def _save_route_state(self, session_id: str, state: dict[str, Any]) -> bool:
        """Persist only routing identifiers; message/business state stays in Bug DB/Dify."""
        base = settings.bugtrack_api_base.rstrip("/")
        if not base:
            return True
        payload = {
            # Keep the route-session API shape for old clients, but never persist
            # a live B route or B conversation from the new runtime.
            "active": "A",
            "conv_a": str(state.get("conv_a") or ""),
            "conv_b": "",
            "route_data": {
                "vague_count": max(0, int(state.get("vague_count") or 0)),
                "vague_exhausted": bool(state.get("vague_exhausted")),
                "bug_v2_active": bool(state.get("bug_v2_active")),
                "bug_v2_suspended": bool(state.get("bug_v2_suspended")),
            },
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
                session_id[:12],
                str(exc)[:120],
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
        message_id: str = "",
        action_id: str = "",
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
                "active": "A",
                "conv_a": "",
                "conv_b": "",
                "bug_v2_active": False,
                "bug_v2_suspended": False,
            }

        # M4: historical route sessions may say B, but B is no longer a live app.
        state["active"] = "A"
        state["conv_b"] = ""
        active = "A"
        selected_action = (action_id or "").strip().lower()
        intent = classify_customer_intent(
            self._reply_policy,
            text=query if text.strip() else "",
            language=lang,
            has_attachments=bool(image_bytes or audio_bytes),
        )
        explicit_events = {
            "bug.confirm_submit": "CONFIRM_SUBMIT",
            "bug.confirm_match": "CONFIRM_MATCH",
            "bug.reject_match": "REJECT_MATCH",
            "bug.cancel": "CANCEL",
            "bug.resume": "RESUME",
        }
        if selected_action == "route.qa":
            state["vague_count"] = 0
            state["vague_exhausted"] = False
            await self._remember_state(session_id, state)
            answer = "请直接发送你想查询的功能、入口或使用问题。"
            return {
                "assistant_text": answer,
                "raw": {"data": {"outputs": {"answer": answer}}},
                "conversation_id": str(state.get("conv_a") or ""),
                "intent": {"intent": "qa", "confidence": 1.0, "entities": {}, "reason": "user_action"},
                "actions": [],
            }
        if selected_action == "route.bug":
            intent = classify_customer_intent(
                self._reply_policy, text="页面报错", language=lang
            )
            if not self._bug_v2_enabled():
                return await self._bug_v2_retry_response(
                    session_id=session_id, state=state, language=lang, keep_session=False
                )
            result = await self._run_bug_v2(
                session_id=session_id,
                query="",
                language=lang,
                message_id=message_id,
                image_bytes=None,
                image_name=None,
                event="START_REPORT",
            )
            return await self._finish_bug_v2(
                session_id=session_id, state=state, result=result
            )

        if state.get("bug_v2_suspended") and (
            selected_action == "bug.resume"
            or re.sub(r"\s+", "", query.lower())
            in {"继续反馈", "恢复反馈", "继续提交", "resume"}
        ):
            if not self._bug_v2_enabled():
                return await self._bug_v2_retry_response(
                    session_id=session_id, state=state, language=lang, keep_session=False
                )
            result = await self._run_bug_v2(
                session_id=session_id,
                query="",
                language=lang,
                message_id=message_id,
                image_bytes=None,
                image_name=None,
                event="RESUME",
            )
            return await self._finish_bug_v2(
                session_id=session_id, state=state, result=result
            )

        if state.get("bug_v2_active"):
            if not self._bug_v2_enabled():
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=True,
                )
            if audio_bytes:
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=True,
                    audio_unsupported=True,
                )
            # A high-confidence knowledge/topic-switch message pauses the draft
            # before it reaches v2. Progress lookup remains read-only and does
            # not mutate the active draft.
            if intent.intent == "bug_progress":
                progress_method = getattr(self._bug_orchestrator, "progress", None)
                if not callable(progress_method):
                    # Compatibility for pre-M5 adapters. The production client
                    # always implements the read-only endpoint above.
                    v2_result = await self._run_bug_v2(
                        session_id=session_id,
                        query=query,
                        language=lang,
                        message_id=message_id,
                        image_bytes=None,
                        image_name=None,
                    )
                    return await self._finish_bug_v2(
                        session_id=session_id, state=state, result=v2_result
                    )
                try:
                    progress = await progress_method(session_id=session_id)
                except (BugOrchestratorError, AttributeError) as exc:
                    log.warning("[ROUTER] Bug progress lookup failed: %s", str(exc)[:120])
                    progress = {"assistant_text": "暂时无法查询问题进度，请稍后重试。", "actions": []}
                answer = str(progress.get("assistant_text") or "暂时没有可显示的进度。")
                return {
                    "assistant_text": answer,
                    "raw": {"data": {"outputs": {"answer": answer, "bug_progress": progress}}},
                    "conversation_id": str(state.get("conv_a") or ""),
                    "intent": intent.to_dict(),
                    "actions": progress.get("actions") or [],
                }
            if (
                selected_action == "bug.suspend"
                or (intent.intent == "qa" and intent.confidence >= 0.9 and not image_bytes and not audio_bytes)
            ):
                try:
                    suspended = await self._run_bug_v2(
                        session_id=session_id, query="", language=lang,
                        message_id=message_id, image_bytes=None, image_name=None,
                        event="SUSPEND",
                    )
                except BugOrchestratorError as exc:
                    log.error("[ROUTER] Bug v2 suspend failed: %s", str(exc)[:160])
                    return await self._bug_v2_retry_response(
                        session_id=session_id, state=state, language=lang, keep_session=True
                    )
                state["bug_v2_active"] = False
                state["bug_v2_suspended"] = True
                await self._remember_state(session_id, state)
                if selected_action == "bug.suspend":
                    return await self._finish_bug_v2(
                        session_id=session_id, state=state, result=suspended
                    )
            else:
                event = explicit_events.get(selected_action, "")
                v2_query = "" if event else query
                try:
                    v2_result = await self._run_bug_v2(
                        session_id=session_id,
                        query=v2_query,
                        language=lang,
                        message_id=message_id,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        event=event,
                    )
                except BugOrchestratorError as exc:
                    log.error(
                        "[ROUTER] Bug v2 continuation failed session=%s error=%s",
                        session_id[:12],
                        str(exc)[:160],
                    )
                    return await self._bug_v2_retry_response(
                        session_id=session_id,
                        state=state,
                        language=lang,
                        keep_session=True,
                    )
                if not v2_result.get("fallback_required"):
                    return await self._finish_bug_v2(
                        session_id=session_id,
                        state=state,
                        result=v2_result,
                    )
                state["bug_v2_active"] = False
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                )

        if state.get("bug_v2_suspended") and selected_action == "bug.cancel":
            try:
                result = await self._run_bug_v2(
                    session_id=session_id, query="", language=lang, message_id=message_id,
                    image_bytes=None, image_name=None, event="CANCEL",
                )
            except BugOrchestratorError:
                return await self._bug_v2_retry_response(
                    session_id=session_id, state=state, language=lang, keep_session=False
                )
            return await self._finish_bug_v2(session_id=session_id, state=state, result=result)

        if state.get("bug_v2_suspended") and intent.intent == "bug_report":
            answer = "你有一份已暂停的问题反馈。请先继续原草稿，或取消后再提交新问题。"
            actions = [
                action("bug.resume", "继续反馈", "primary"),
                action("bug.cancel", "取消反馈"),
            ]
            return {
                "assistant_text": answer,
                "raw": {"data": {"outputs": {"answer": answer, "intent": intent.to_dict(), "actions": actions}}},
                "conversation_id": str(state.get("conv_a") or ""),
                "intent": intent.to_dict(),
                "actions": actions,
            }

        normalized_query = re.sub(r"[\s，。！？、,.!?;；:：]+", "", query.lower())
        if (
            not state.get("bug_v2_suspended")
            and not selected_action
            and normalized_query
            in {
                "我要咨询",
                "咨询一下",
                "我有问题",
                "需要帮助",
                "我要反馈",
                "反馈问题",
                "i need help",
            }
            and not image_bytes
            and not audio_bytes
        ):
            answer = "你想查询解决方法，还是提交问题反馈？"
            actions = [
                action("route.qa", "查询解决方法", "primary"),
                action("route.bug", "提交问题反馈"),
            ]
            return {
                "assistant_text": answer,
                "raw": {"data": {"outputs": {"answer": answer, "intent": intent.to_dict(), "actions": actions}}},
                "conversation_id": str(state.get("conv_a") or ""),
                "intent": intent.to_dict(),
                "actions": actions,
            }

        policy_reply = self._reply_policy.evaluate(
            text=query,
            language=lang,
            active_app=active,
            has_attachments=bool(image_bytes or audio_bytes),
            vague_count=max(0, int(state.get("vague_count") or 0)),
            vague_exhausted=bool(state.get("vague_exhausted")),
        )
        if policy_reply is not None:
            if policy_reply.route.startswith("vague_"):
                state["vague_count"] = policy_reply.vague_count
                state["vague_exhausted"] = policy_reply.vague_exhausted
            else:
                state["vague_count"] = 0
                state["vague_exhausted"] = False
            if policy_reply.route.startswith("verified_"):
                # A verified FAQ is a clear topic switch away from a Bug draft.
                state["active"] = "A"
                state["bug_v2_active"] = False
                active = "A"
            async with self._lock:
                self._store[session_id] = {
                    "state": state,
                    "ts": time.monotonic(),
                }
            await self._save_route_state(session_id, state)
            log.info(
                "[ROUTER] deterministic route=%s session=%s active=%s",
                policy_reply.route,
                session_id[:12],
                active,
            )
            normalized_raw = {
                "data": {
                    "outputs": {
                        "output": policy_reply.text,
                        "answer": policy_reply.text,
                        "policy_route": policy_reply.route,
                    }
                },
                "conversation_id": state.get("conv_a") or "",
            }
            return {
                "assistant_text": policy_reply.text,
                "raw": normalized_raw,
                "conversation_id": normalized_raw["conversation_id"],
                "intent": intent.to_dict(),
                "actions": (
                    [action("bug.resume", "继续反馈", "primary"), action("bug.cancel", "取消反馈")]
                    if state.get("bug_v2_suspended") else []
                ),
            }

        target_app = self._reply_policy.route_target(
            text=query,
            active_app=active,
            has_attachments=bool(image_bytes or audio_bytes),
        )
        if target_app == "B":
            # Bug意图只能进入编排服务。语音暂不支持；服务异常和候选回退
            # 都明确要求重试，绝不把原消息送入 Dify A/B。
            if audio_bytes:
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                    audio_unsupported=True,
                )
            if not self._bug_v2_enabled():
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                )
            try:
                v2_result = await self._run_bug_v2(
                    session_id=session_id,
                    query=query,
                    language=lang,
                    message_id=message_id,
                    image_bytes=image_bytes,
                    image_name=image_name,
                )
            except BugOrchestratorError as exc:
                log.error(
                    "[ROUTER] Bug v2 initial failed session=%s error=%s",
                    session_id[:12],
                    str(exc)[:160],
                )
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                )
            if v2_result.get("fallback_required"):
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                )
            return await self._finish_bug_v2(
                session_id=session_id,
                state=state,
                result=v2_result,
            )

        state["vague_count"] = 0
        state["vague_exhausted"] = False
        client = self._client_a
        conv_id = str(state.get("conv_a") or "")
        files = await self._build_files(
            client, image_bytes, image_name, audio_bytes, audio_name
        )

        raw = await self._call(client, query, inputs, files, conv_id)
        answer = (raw or {}).get("answer") or ""
        new_conv = (raw or {}).get("conversation_id") or ""
        if new_conv:
            state["conv_a"] = new_conv

        # Dify A 可能仍返回历史 Bug 切换标记。M4 不再调用 Dify B，
        # 但该标记可作为意图门控漏判时的兼容信号，改投 v2 编排服务。
        answer, switch_markers = parse_switch_markers(answer)
        if SWITCH_TO_BUG in switch_markers:
            state["conv_a"] = ""
            state["vague_count"] = 0
            state["vague_exhausted"] = False
            new_conv = ""
        if SWITCH_TO_BUG in switch_markers and self._reply_policy.blocks_bug_route(
            query
        ):
            log.warning(
                "[ROUTER] ignored legacy Bug marker for non-Bug query session=%s",
                session_id[:12],
            )
            answer = self._reply_policy.non_bug_marker_reply(lang, query)
        elif SWITCH_TO_BUG in switch_markers:
            log.warning(
                "[ROUTER] legacy Bug marker rerouted to v2 session=%s",
                session_id[:12],
            )
            if audio_bytes:
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                    audio_unsupported=True,
                )
            if not self._bug_v2_enabled():
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                )
            try:
                v2_result = await self._run_bug_v2(
                    session_id=session_id,
                    query=query,
                    language=lang,
                    message_id=message_id,
                    image_bytes=image_bytes,
                    image_name=image_name,
                )
            except BugOrchestratorError as exc:
                log.error(
                    "[ROUTER] legacy Bug marker v2 reroute failed session=%s error=%s",
                    session_id[:12],
                    str(exc)[:160],
                )
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                )
            if v2_result.get("fallback_required"):
                return await self._bug_v2_retry_response(
                    session_id=session_id,
                    state=state,
                    language=lang,
                    keep_session=False,
                )
            return await self._finish_bug_v2(
                session_id=session_id,
                state=state,
                result=v2_result,
            )

        # 剥离所有 <!--SYS:...--> 控制标记 (SWITCH 残留 + TIMER 等 WeCom 协议标记)。
        # H5 不作用于这些协议标记, 统一从用户可见文本移除。
        answer = strip_sys_markers(answer)
        if not answer.strip():
            answer = "抱歉，我暂时无法处理该消息，请稍后重试。"

        async with self._lock:
            self._store[session_id] = {"state": state, "ts": time.monotonic()}
            # lazy 清理过期项, 防长期累积 (阈值触发扫描, 避免每次请求开销)
            if len(self._store) > 512:
                cutoff = time.monotonic() - self._SESSION_TTL
                for k in [
                    k for k, v in self._store.items() if v.get("ts", 0.0) <= cutoff
                ]:
                    self._store.pop(k, None)

        await self._save_route_state(session_id, state)

        log.info(
            "[ROUTER] session=%s active=A conv_a=%s answer_len=%d",
            session_id[:12],
            (state.get("conv_a") or "")[:8],
            len(answer),
        )

        # 归一化为 workflow 形态, 复用 response_parser 抽取 text + media
        normalized_raw = {
            "data": {"outputs": {"output": answer, "answer": answer}},
            "conversation_id": new_conv,
        }
        return {
            "assistant_text": answer,
            "raw": normalized_raw,
            "conversation_id": new_conv,
            "intent": intent.to_dict(),
            "actions": (
                [action("bug.resume", "继续反馈", "primary"), action("bug.cancel", "取消反馈")]
                if state.get("bug_v2_suspended") else []
            ),
        }


router = ChatflowRouter(
    api_base=settings.dify_api_base,
    key_a=settings.api_key_a,
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
        "dual_app": False,
        "bugtrack_image_cache": bool(settings.bugtrack_api_base),
        "bugtrack_orchestrator_mode": settings.bugtrack_orchestrator_mode,
        "bugtrack_orchestrator_active": router._bug_v2_enabled(),
    }


@app.get("/api/notifications", response_model=None)
async def notifications(
    limit: int = 20,
    sid: str = Depends(_notification_session),
) -> dict[str, Any] | JSONResponse:
    if not router._bug_orchestrator.enabled:
        return {"notifications": []}
    try:
        items = await router._bug_orchestrator.notifications(
            session_id=sid, limit=max(1, min(limit, 100))
        )
    except BugOrchestratorError as exc:
        log.warning("Bug notification fetch failed session=%s: %s", sid[:12], exc)
        return JSONResponse(
            status_code=502, content={"detail": "Bug notification service unavailable"}
        )
    return {"notifications": items}


@app.post("/api/notifications/ack", response_model=None)
async def acknowledge_notifications(
    req: NotificationAckRequest,
    sid: str = Depends(_notification_session),
) -> dict[str, Any] | JSONResponse:
    if not router._bug_orchestrator.enabled:
        return {"acknowledged": 0}
    try:
        count = await router._bug_orchestrator.acknowledge_notifications(
            session_id=sid,
            notification_ids=req.notification_ids,
        )
    except BugOrchestratorError as exc:
        log.warning("Bug notification ack failed session=%s: %s", sid[:12], exc)
        return JSONResponse(
            status_code=502, content={"detail": "Bug notification service unavailable"}
        )
    return {"acknowledged": count}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    text: str = Form(""),
    image: Optional[UploadFile] = File(default=None),
    audio: Optional[UploadFile] = File(default=None),
    language: str = Form(""),
    session_id: Optional[str] = Form(default=None),
    message_id: Optional[str] = Form(default=None),
    action_id: Optional[str] = Form(default=None),
) -> ChatResponse:
    # session_id: 前端 localStorage 持久化; 首次不传则后端生成并回传
    sid = (session_id or "").strip() or f"h5-{uuid.uuid4().hex}"
    mid = (message_id or "").strip() or f"h5msg-{uuid.uuid4().hex}"

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
            message_id=mid,
            action_id=(action_id or "").strip(),
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
    except BugOrchestratorError as e:
        log.error("Bug orchestrator error: %s", e)
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Bug 提交服务暂时不可用，请稍后重试",
                "session_id": sid,
            },
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
        intent=IntentPayload(**result["intent"]) if result.get("intent") else None,
        actions=[ActionItem(**item) for item in result.get("actions") or []],
    )
