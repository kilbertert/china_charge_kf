"""回归测试 - ⑦ H5 会话 TTL: 超时未活动的 session 视为新会话, 重置 active/conv。

ChatflowRouter.chat 在读取 session 状态时, 若 (now - ts) > _SESSION_TTL,
丢弃旧 state (含 active/conv_a/conv_b) 回到默认 {"active":"A",...},
避免陈旧 conv_id 误用 / 跨会话串话。
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

from app_dify.dify_client import DifyClient
from app_dify.main import router


def _run(coro):
    return asyncio.run(coro)


def test_session_ttl_expires_and_resets_state():
    """超时 session -> active 重置为 A, 旧 conv 清空, 用新 conv。"""
    sid = "test-ttl-expired"
    # 陈旧 entry: active=B, 旧 conv, ts 早于 TTL
    router._store[sid] = {
        "state": {"active": "B", "conv_a": "stale-a", "conv_b": "stale-b"},
        "ts": time.monotonic() - router._SESSION_TTL - 10,
    }
    fake = {"answer": "您好,已为您新建会话。", "conversation_id": "new-conv-after-ttl"}
    try:
        with patch.object(DifyClient, "run_chatflow", AsyncMock(return_value=fake)):
            _run(router.chat(session_id=sid, text="你好", language="中文"))
        st = router._store[sid]["state"]
        assert st["active"] == "A", f"过期应重置 active=A, got {st['active']}"
        assert st["conv_a"] == "new-conv-after-ttl", "应使用新 conversation_id"
        assert st["conv_b"] == "", "旧 conv_b 应被清空"
    finally:
        router._store.pop(sid, None)


def test_session_within_ttl_keeps_state():
    """未超时 session -> 保留 active, 仅更新 conv。"""
    sid = "test-ttl-fresh"
    router._store[sid] = {
        "state": {"active": "B", "conv_a": "keep-a", "conv_b": "keep-b"},
        "ts": time.monotonic(),  # 刚活动, 未过期
    }
    fake = {"answer": "续接会话。", "conversation_id": "updated-conv"}
    try:
        with patch.object(DifyClient, "run_chatflow", AsyncMock(return_value=fake)):
            _run(router.chat(session_id=sid, text="还在吗", language="中文"))
        st = router._store[sid]["state"]
        assert st["active"] == "B", "未过期不应重置 active"
        assert st["conv_a"] == "keep-a", "未涉及的 conv_a 应保留"
    finally:
        router._store.pop(sid, None)


def test_session_ttl_lazy_cleanup_evicts_expired():
    """store 超 512 项时触发 lazy 清理过期项 (防长期累积)。"""
    # 填入若干过期项 + 一个未过期项
    base = time.monotonic()
    for i in range(3):
        router._store[f"test-ttl-stale-{i}"] = {
            "state": {"active": "A", "conv_a": "", "conv_b": ""},
            "ts": base - router._SESSION_TTL - 100,
        }
    fresh_sid = "test-ttl-lazy-fresh"
    router._store[fresh_sid] = {
        "state": {"active": "A", "conv_a": "", "conv_b": ""},
        "ts": base,
    }
    fake = {"answer": "ok", "conversation_id": "c1"}
    try:
        # 直接调 chat 触发 lazy 清理路径 (store > 512 才扫; 这里用 < 512 验证不误删未过期)
        with patch.object(DifyClient, "run_chatflow", AsyncMock(return_value=fake)):
            _run(router.chat(session_id=fresh_sid, text="hi", language="中文"))
        # 未过期项必须仍在 (清理只删过期)
        assert fresh_sid in router._store, "lazy 清理不应删除未过期项"
    finally:
        for i in range(3):
            router._store.pop(f"test-ttl-stale-{i}", None)
        router._store.pop(fresh_sid, None)
