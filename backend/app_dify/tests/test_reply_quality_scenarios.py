"""Stateful customer scenarios for the Bug v2 reply strategy."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app_dify.config import settings
from app_dify.dify_client import DifyClient
from app_dify.main import app, router


def test_duplicate_progress_and_new_clue_stay_in_one_customer_session() -> None:
    session_id = "reply-quality-multiturn"
    responses = [
        {
            "assistant_text": "已进入问题追踪流程，请确认问题信息。",
            "state": "ready_to_submit",
            "continue_session": True,
            "fallback_required": False,
        },
        {
            "assistant_text": "您反馈的问题当前进度如下：\n当前状态:开发中",
            "state": "collecting",
            "continue_session": True,
            "fallback_required": False,
        },
        {
            "assistant_text": "已按新的设备白名单线索重新查重，请确认。",
            "state": "ready_to_submit",
            "continue_session": True,
            "fallback_required": False,
        },
    ]
    fake = type("FakeBugOrchestrator", (), {"enabled": True})()
    fake.message = AsyncMock(side_effect=responses)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as run,
        ):
            client = TestClient(app)
            first = client.post(
                "/api/chat",
                data={"text": "订单结算失败", "session_id": session_id},
            )
            progress = client.post(
                "/api/chat",
                data={"text": "这个问题解决了吗", "session_id": session_id},
            )
            new_clue = client.post(
                "/api/chat",
                data={
                    "text": "不是，是设备白名单新增失败",
                    "session_id": session_id,
                },
            )

        assert first.status_code == 200
        assert progress.status_code == 200
        assert new_clue.status_code == 200
        assert "当前进度如下" in progress.json()["assistant_text"]
        assert "重新查重" in new_clue.json()["assistant_text"]
        run.assert_not_awaited()
        assert fake.message.await_count == 3
        assert fake.message.await_args_list[1].kwargs["text"] == "这个问题解决了吗"
        assert (
            fake.message.await_args_list[2].kwargs["text"]
            == "不是，是设备白名单新增失败"
        )
        assert router._store[session_id]["state"]["conv_a"] == ""
        assert router._store[session_id]["state"]["conv_b"] == ""
        assert router._store[session_id]["state"]["active"] == "A"
        assert router._store[session_id]["state"]["bug_v2_active"] is True
    finally:
        router._store.pop(session_id, None)
