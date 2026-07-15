"""Dify 转发层 — 复用 app_dify.dify_client。

复用策略: 与 health_consult 一致,通过 sys.path hack 引用 app_dify。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

_BACKEND_ROOT = str(Path(__file__).resolve().parents[1])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app_dify.dify_client import DifyClient, DifyError  # noqa: E402

from .config import settings  # noqa: E402
from .scene_router import build_local_fallback  # noqa: E402

log = logging.getLogger("charge_consult.dify_proxy")


class DifyProxyError(RuntimeError):
    """Raised when Dify proxy fails irrecoverably (caller decides fallback)."""


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


async def chat_with_dify(
    text: str,
    session_id: str = "",
    inputs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """调用 Dify workflow,返回原始 response dict。

    Raises:
        DifyProxyError: 当 Dify 调用失败或配置缺失
    """
    if not settings.dify_api_key:
        raise DifyProxyError("DIFY_API_KEY not configured")

    client = get_dify_client()
    payload_inputs = inputs or {}
    if session_id:
        payload_inputs["session_id"] = session_id

    try:
        result = await client.run_workflow(
            inputs=payload_inputs,
            response_mode="blocking",
        )
    except DifyError as e:
        log.warning("Dify call failed: %s", e)
        raise DifyProxyError(str(e)) from e

    return result


def parse_dify_output(raw: dict[str, Any]) -> dict[str, Any]:
    """从 Dify workflow 输出中提取 SceneResponse JSON。

    Dify workflow 的 5099 end 节点 output 是一个 JSON 字符串,
    我们尝试解析,失败时返回原始 dict(由调用方决定如何处理)。
    """
    output = raw.get("data", {}).get("outputs", {}).get("output") or raw.get("output")
    if isinstance(output, str):
        try:
            return json.loads(output)
        except (ValueError, TypeError):
            log.warning("Dify output not valid JSON, returning raw")
            return {"_raw_output": output, "_raw_full": raw}
    if isinstance(output, dict):
        return output
    return {"_raw_full": raw}


async def chat_with_fallback(
    text: str,
    language: str = "zh",
    session_id: str = "",
    hint_endpoint: Optional[str] = None,
    hint_region: Optional[str] = None,
    inputs: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], str]:
    """Dify 调用 + 本地兜底。

    Returns:
        (parsed_output, source) where source ∈ {"dify", "local_fallback", "hybrid"}
    """
    try:
        raw = await chat_with_dify(text, session_id=session_id, inputs=inputs)
        parsed = parse_dify_output(raw)
        return parsed, "dify"
    except DifyProxyError as e:
        log.warning("Dify unavailable, falling back to local: %s", e)
        fallback = build_local_fallback(
            text=text,
            language=language,
            hint_endpoint=hint_endpoint,
            hint_region=hint_region,
        )
        return fallback.model_dump(mode="json"), "local_fallback"
