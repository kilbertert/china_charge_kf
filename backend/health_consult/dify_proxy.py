"""Dify 转发层 — 复用 app_dify.dify_client。

复用策略:
  - `app_dify.dify_client.DifyClient` 通过 sys.path hack 直接 import;
    长期应该重构到共享位置(如 backend/dify_sdk/),本 MVP 先保留。
  - 复用 `app_dify.response_parser` 的 `_safe_url` / `_normalize_media_item`
    工具(目前 health_consult 不解析 media,留 TODO)。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

# 把 backend/ 目录加到 sys.path,这样 `from app_dify.dify_client import DifyClient` 才能解析。
# Path: backend/health_consult/dify_proxy.py → parents[1] = backend/
_BACKEND_ROOT = str(Path(__file__).resolve().parents[1])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app_dify.dify_client import DifyClient, DifyError  # noqa: E402

from .config import settings  # noqa: E402
from .scene_router import get_default_scene_response  # noqa: E402

log = logging.getLogger("health_consult.dify_proxy")


class DifyProxyError(RuntimeError):
    """Raised when Dify proxy fails irrecoverably (caller decides whether to fallback)."""


# ── 单例 DifyClient ────────────────────────────────────────────
_client: Optional[DifyClient] = None


def get_dify_client() -> DifyClient:
    """返回 DifyClient 单例。"""
    global _client
    if _client is None:
        _client = DifyClient(
            api_base=settings.dify_api_base,
            api_key=settings.dify_api_key,
            end_user=settings.dify_end_user,
        )
    return _client


# ── 文件上传辅助 ───────────────────────────────────────────────
def _dify_file_type(content_type: str, filename: str) -> str:
    """根据 MIME/文件名映射 Dify file type (image/document/audio/video)。

    Dify file_ref 的 type 决定下游节点路由: image->vision, document->文档解析/RAG。
    错配(如 PDF 标 image)会导致 vision 节点处理失败。未知二进制兜底 document。
    """
    ct = (content_type or "").lower()
    name = (filename or "").lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("audio/"):
        return "audio"
    if ct.startswith("video/"):
        return "video"
    if ct.startswith("application/pdf") or name.endswith(".pdf"):
        return "document"
    if "word" in ct or name.endswith((".doc", ".docx")):
        return "document"
    if "sheet" in ct or name.endswith((".xls", ".xlsx", ".csv")):
        return "document"
    if ct.startswith("text/") or name.endswith((".txt", ".md")):
        return "document"
    return "document"


async def _upload_files(client: DifyClient, files: list[Any]) -> list[tuple[str, str]]:
    """上传多个文件到 Dify,返回 (upload_file_id, dify_file_type) 列表。"""
    uploaded: list[tuple[str, str]] = []
    for f in files:
        try:
            content = await f.read()
        except Exception as e:  # noqa: BLE001
            log.warning("read uploaded file failed: %s", e)
            continue
        if not content:
            continue
        ct = f.content_type or "application/octet-stream"
        fname = f.filename or "file"
        try:
            fid = await client.upload_file(filename=fname, content=content, content_type=ct)
            uploaded.append((fid, _dify_file_type(ct, fname)))
        except DifyError as e:
            log.warning("Dify upload_file failed: %s", e)
            continue
    return uploaded


# ── 主入口 ────────────────────────────────────────────────────
async def chat_with_dify(
    *,
    text: str = "",
    files: Optional[list[Any]] = None,
    answers: Optional[dict] = None,
    session_id: str = "",
    language: str = "中文",
) -> dict[str, Any]:
    """调用 Dify workflow,返回 SceneResponse dict。

    失败策略:
      - Dify 不可达 / workflow 失败 → 抛出 DifyProxyError,
        由 endpoint 层 catch 后退到本地 scene_router。
    """
    if not settings.dify_api_key:
        raise DifyProxyError("DIFY_API_KEY not configured")

    client = get_dify_client()
    uploaded: list[tuple[str, str]] = []
    if files:
        uploaded = await _upload_files(client, files)

    # 组装 workflow inputs
    answers_str = json.dumps(answers or {}, ensure_ascii=False)
    inputs: dict[str, Any] = {
        settings.dify_input_text: text or "",
        settings.dify_input_language: language,
        settings.dify_input_answers: answers_str,
    }
    if session_id:
        inputs[settings.dify_input_session_id] = session_id
    if uploaded:
        inputs[settings.dify_input_image] = [
            client.file_ref(uid, ftype) for uid, ftype in uploaded
        ]

    try:
        body = await client.run_workflow(inputs=inputs, response_mode="blocking")
    except DifyError as e:
        log.error("Dify workflow failed: %s", e)
        raise DifyProxyError(f"Dify workflow error: {e}") from e

    # 解析 workflow outputs
    outputs = ((body or {}).get("data") or {}).get("outputs") or {}
    raw_text = outputs.get(settings.dify_output_text)
    parsed: Optional[dict] = None
    if isinstance(raw_text, str) and raw_text.strip():
        try:
            candidate = json.loads(raw_text)
            if isinstance(candidate, dict):
                parsed = candidate
        except (ValueError, TypeError):
            parsed = None

    if parsed is None:
        # workflow 没按 JSON 约定输出,退到本地兜底
        log.warning("Dify output not JSON-decodeable; falling back. raw=%s", raw_text)
        return get_default_scene_response(text=text, answers=answers)

    # 期望结构: {scene, risk_level, confidence, payload}
    scene = parsed.get("scene") or "symptom"
    risk_level = parsed.get("risk_level") or "low"
    confidence = parsed.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 1.0
    payload = parsed.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    return {
        "scene": scene,
        "risk_level": risk_level,
        "confidence": float(confidence),
        "payload": payload,
        "raw": body,
    }
