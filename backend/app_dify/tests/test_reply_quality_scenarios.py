"""Stateful customer scenarios for the A/B reply strategy."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app_dify.dify_client import DifyClient
from app_dify.main import app, router


def test_duplicate_progress_and_new_clue_stay_in_one_customer_session() -> None:
    session_id = "reply-quality-multiturn"
    old_dual = router._dual
    old_client_b = router._client_b
    router._dual = True
    router._client_b = DifyClient("http://dify.test/v1", "app-test-b", "test-user")

    responses = [
        {"answer": "<!--SYS:SWITCH_TO_BUG-->", "conversation_id": "conv-a"},
        {
            "answer": "已进入问题追踪流程，请确认问题信息。",
            "conversation_id": "conv-b",
        },
        {
            "answer": "您反馈的问题当前进度如下：\n当前状态:开发中",
            "conversation_id": "conv-b",
        },
        {
            "answer": "已按新的设备白名单线索重新查重，请确认。",
            "conversation_id": "conv-b",
        },
    ]
    try:
        with patch.object(
            DifyClient, "run_chatflow", AsyncMock(side_effect=responses)
        ) as run:
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
        assert run.await_count == 4
        assert run.await_args_list[0].kwargs["conversation_id"] == ""
        assert run.await_args_list[1].kwargs["conversation_id"] == ""
        assert run.await_args_list[2].kwargs["conversation_id"] == "conv-b"
        assert run.await_args_list[3].kwargs["conversation_id"] == "conv-b"
        assert router._store[session_id]["state"]["active"] == "B"
    finally:
        router._store.pop(session_id, None)
        router._dual = old_dual
        router._client_b = old_client_b
