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
        with (
            patch.object(DifyClient, "run_chatflow", AsyncMock(return_value=fake)),
            patch.object(router, "_load_route_state", AsyncMock(return_value=None)),
        ):
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
    """store 超 512 项时触发 lazy 清理: 过期项被移除, 未过期项保留。

    复审 P2: 旧版只加 4 项 (<512) 没真正触发 cleanup 分支。这里加 513 过期项 +
    1 fresh = 514 > 512, 断言过期项全清、fresh 保留。
    """
    base = time.monotonic()
    stale_prefix = "test-ttl-stale-"
    # 513 个过期项 (ts 早于 TTL)
    for i in range(513):
        router._store[f"{stale_prefix}{i}"] = {
            "state": {"active": "A", "conv_a": "", "conv_b": ""},
            "ts": base - router._SESSION_TTL - 100,
        }
    assert len(router._store) >= 513
    fresh_sid = "test-ttl-lazy-fresh"
    fake = {"answer": "ok", "conversation_id": "c1"}
    try:
        with patch.object(DifyClient, "run_chatflow", AsyncMock(return_value=fake)):
            _run(router.chat(session_id=fresh_sid, text="hi", language="中文"))
        # chat 保存 fresh 后 store=514 > 512 -> 触发清理: 513 过期项应全部移除
        remaining_stale = [k for k in router._store if k.startswith(stale_prefix)]
        assert remaining_stale == [], f"过期项未清理: 残留 {len(remaining_stale)}"
        # 未过期的 fresh 项保留 (ts 刚写入 > cutoff)
        assert fresh_sid in router._store, "未过期项不应被清理"
    finally:
        for k in [k for k in list(router._store) if k.startswith(stale_prefix) or k == fresh_sid]:
            router._store.pop(k, None)


def test_session_restores_route_from_relational_store_after_process_restart():
    sid = "test-route-restore"
    router._store.pop(sid, None)
    fake = {"answer": "继续确认。", "conversation_id": "conv-b-restored-next"}
    try:
        with (
            patch.object(
                router,
                "_load_route_state",
                AsyncMock(
                    return_value={
                        "active": "B",
                        "conv_a": "conv-a-restored",
                        "conv_b": "conv-b-restored",
                    }
                ),
            ),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "run_chatflow", AsyncMock(return_value=fake)) as run,
        ):
            _run(router.chat(session_id=sid, text="确认", language="中文"))
        assert run.await_args.kwargs["conversation_id"] == "conv-b-restored"
        assert router._store[sid]["state"]["active"] == "B"
        assert router._store[sid]["state"]["conv_b"] == "conv-b-restored-next"
    finally:
        router._store.pop(sid, None)
