"""M2 H5 routing contract for the deterministic Bug orchestrator."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app_dify.bug_orchestrator_client import BugOrchestratorError
from app_dify.config import settings
from app_dify.dify_client import DifyClient
from app_dify.main import app, router

client = TestClient(app)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"m2-h5-image"


class FakeBugOrchestrator:
    enabled = True

    def __init__(self, *, result=None, side_effect=None) -> None:
        self.message = AsyncMock(return_value=result, side_effect=side_effect)
        self.notifications = AsyncMock(return_value=[])
        self.acknowledge_notifications = AsyncMock(return_value=0)


def _post(
    text: str,
    session_id: str,
    *,
    message_id: str,
    image: bool = False,
):
    files = None
    if image:
        files = {"image": ("screen.png", PNG_BYTES, "image/png")}
    response = client.post(
        "/api/chat",
        data={
            "text": text,
            "session_id": session_id,
            "message_id": message_id,
            "language": "中文",
        },
        files=files,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _ready_result() -> dict:
    return {
        "success": True,
        "assistant_text": "我已整理本次问题，请回复“确认提交”。",
        "state": "ready_to_submit",
        "draft_id": "draft-v2",
        "continue_session": True,
        "fallback_required": False,
        "fallback_text": "",
        "sync_pending": False,
    }


def _submitted_result() -> dict:
    return {
        "success": True,
        "assistant_text": "反馈已记录，编号：rec-v2。",
        "state": "submitted",
        "draft_id": "draft-v2",
        "record_id": "rec-v2",
        "continue_session": False,
        "fallback_required": False,
        "fallback_text": "",
        "sync_pending": False,
    }


def test_obvious_bug_uses_v2_without_calling_dify_b() -> None:
    sid = "m2-h5-direct"
    fake = FakeBugOrchestrator(result=_ready_result())
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(settings, "bugtrack_orchestrator_fallback_to_dify_b", True),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as dify,
        ):
            body = _post("订单结算失败", sid, message_id="msg-direct")

        assert "确认提交" in body["assistant_text"]
        fake.message.assert_awaited_once()
        assert fake.message.await_args.kwargs["message_id"] == "msg-direct"
        dify.assert_not_awaited()
        state = router._store[sid]["state"]
        assert state["active"] == "A"
        assert state["bug_v2_active"] is True
    finally:
        router._store.pop(sid, None)


def test_confirmation_turn_goes_directly_to_v2() -> None:
    sid = "m2-h5-confirm"
    fake = FakeBugOrchestrator(side_effect=[_ready_result(), _submitted_result()])
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as dify,
        ):
            _post("订单结算失败", sid, message_id="msg-first")
            body = _post("确认提交", sid, message_id="msg-confirm")

        assert body["assistant_text"] == "反馈已记录，编号：rec-v2。"
        assert fake.message.await_count == 2
        assert fake.message.await_args_list[1].kwargs["text"] == "确认提交"
        assert fake.message.await_args_list[1].kwargs["message_id"] == "msg-confirm"
        dify.assert_not_awaited()
        assert router._store[sid]["state"]["bug_v2_active"] is False
    finally:
        router._store.pop(sid, None)


def test_prequeue_fallback_never_routes_to_b() -> None:
    sid = "m2-h5-candidate-fallback"
    fallback_text = "Web 后台订单结算失败，点击重试后仍然报错"
    fake = FakeBugOrchestrator(
        result={
            "success": True,
            "assistant_text": "",
            "state": "legacy_fallback",
            "continue_session": False,
            "fallback_required": True,
            "fallback_text": fallback_text,
            "sync_pending": False,
        }
    )
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    return_value={
                        "answer": "已进入旧问题追踪流程。",
                        "conversation_id": "conv-b-fallback",
                    }
                ),
            ) as dify,
        ):
            body = _post("订单结算失败", sid, message_id="msg-candidate")

        assert "尚未处理" in body["assistant_text"]
        dify.assert_not_awaited()
        assert router._store[sid]["state"]["active"] == "A"
        assert router._store[sid]["state"]["conv_b"] == ""
        assert router._store[sid]["state"]["bug_v2_active"] is False
    finally:
        router._store.pop(sid, None)


def test_candidate_confirmation_stays_in_v2_and_never_calls_b() -> None:
    sid = "m3-h5-candidate-confirm"
    candidate = {
        "external_record_id": "rec-existing",
        "module": "订单管理",
        "operation_description": "Web 后台订单结算失败",
        "status": "开发中",
    }
    fake = FakeBugOrchestrator(
        side_effect=[
            {
                "success": True,
                "assistant_text": "找到可能相同的问题，请确认。",
                "state": "awaiting_match_confirmation",
                "draft_id": "draft-existing",
                "continue_session": True,
                "fallback_required": False,
                "candidate": candidate,
            },
            {
                "success": True,
                "assistant_text": "已关联，后续状态变化会通知您。",
                "state": "linked_existing",
                "draft_id": "draft-existing",
                "issue_id": "issue-existing",
                "report_id": "report-occurrence",
                "record_id": "rec-existing",
                "continue_session": False,
                "fallback_required": False,
                "candidate": candidate,
            },
        ]
    )
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as dify,
        ):
            first = _post("订单结算失败", sid, message_id="msg-candidate")
            confirmed = _post("确认相同", sid, message_id="msg-match")

        assert "请确认" in first["assistant_text"]
        assert "状态变化" in confirmed["assistant_text"]
        assert fake.message.await_count == 2
        assert fake.message.await_args_list[1].kwargs["text"] == "确认相同"
        dify.assert_not_awaited()
        assert router._store[sid]["state"]["active"] == "A"
        assert router._store[sid]["state"]["bug_v2_active"] is False
    finally:
        router._store.pop(sid, None)


def test_h5_notification_proxy_fetches_and_acknowledges() -> None:
    fake = FakeBugOrchestrator()
    fake.notifications.return_value = [
        {
            "notification_id": "notice-1",
            "message": "您订阅的问题有新进展：已完成",
        }
    ]
    fake.acknowledge_notifications.return_value = 1
    with patch.object(router, "_bug_orchestrator", fake):
        fetched = client.get("/api/notifications", params={"session_id": "h5-session"})
        acknowledged = client.post(
            "/api/notifications/ack",
            json={
                "session_id": "h5-session",
                "notification_ids": ["notice-1"],
            },
        )

    assert fetched.status_code == 200
    assert fetched.json()["notifications"][0]["notification_id"] == "notice-1"
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged"] == 1
    fake.notifications.assert_awaited_once_with(session_id="h5-session", limit=20)
    fake.acknowledge_notifications.assert_awaited_once_with(
        session_id="h5-session", notification_ids=["notice-1"]
    )


def test_bug_image_goes_to_v2_without_dify_upload() -> None:
    sid = "m2-h5-image"
    fake = FakeBugOrchestrator(result=_ready_result())
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "upload_file", AsyncMock()) as upload,
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as dify,
        ):
            _post(
                "订单结算失败，请看截图",
                sid,
                message_id="msg-image",
                image=True,
            )

        kwargs = fake.message.await_args.kwargs
        assert kwargs["image_bytes"] == PNG_BYTES
        assert kwargs["image_mime"] == "image/png"
        upload.assert_not_awaited()
        dify.assert_not_awaited()
    finally:
        router._store.pop(sid, None)


def test_v2_continuation_failure_keeps_session_and_never_routes_confirmation() -> None:
    sid = "m2-h5-continuation-failure"
    fake = FakeBugOrchestrator(side_effect=BugOrchestratorError("timeout"))
    router._store[sid] = {
        "state": {
            "active": "A",
            "conv_a": "conv-a",
            "conv_b": "",
            "bug_v2_active": True,
        },
        "ts": time.monotonic(),
    }
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as dify,
        ):
            body = _post("确认提交", sid, message_id="msg-retry")

        assert "尚未处理" in body["assistant_text"]
        dify.assert_not_awaited()
        assert router._store[sid]["state"]["active"] == "A"
        assert router._store[sid]["state"]["bug_v2_active"] is True
    finally:
        router._store.pop(sid, None)


def test_a_switch_marker_is_rerouted_to_v2_without_triggering_b() -> None:
    sid = "m2-h5-a-marker"
    fake = FakeBugOrchestrator(result=_ready_result())
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    return_value={
                        "answer": "<!--SYS:SWITCH_TO_BUG-->",
                        "conversation_id": "conv-a-marker",
                    }
                ),
            ) as dify,
        ):
            body = _post(
                "我想咨询一个系统现象",
                sid,
                message_id="msg-marker",
            )

        assert body["assistant_text"] == "我已整理本次问题，请回复“确认提交”。"
        assert dify.await_count == 1
        fake.message.assert_awaited_once()
        assert fake.message.await_args.kwargs["text"] == "我想咨询一个系统现象"
        assert router._store[sid]["state"]["active"] == "A"
        assert router._store[sid]["state"]["conv_a"] == ""
        assert router._store[sid]["state"]["conv_b"] == ""
        assert router._store[sid]["state"]["bug_v2_active"] is True
    finally:
        router._store.pop(sid, None)


def test_a_switch_marker_cannot_override_explicit_non_bug_question() -> None:
    sid = "m2-h5-a-marker-non-bug"
    fake = FakeBugOrchestrator(result=_ready_result())
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    return_value={
                        "answer": "<!--SYS:SWITCH_TO_BUG-->",
                        "conversation_id": "conv-a-marker-faq",
                    }
                ),
            ),
        ):
            body = _post(
                "如何避免操作错误？",
                sid,
                message_id="msg-marker-faq",
            )

        assert "未创建问题反馈" in body["assistant_text"]
        fake.message.assert_not_awaited()
        assert router._store[sid]["state"]["conv_a"] == ""
        assert router._store[sid]["state"]["bug_v2_active"] is False
    finally:
        router._store.pop(sid, None)


def test_a_switch_marker_v2_failure_is_retryable_and_clears_context() -> None:
    sid = "m2-h5-a-marker-failed"
    fake = FakeBugOrchestrator(side_effect=BugOrchestratorError("timeout"))
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    return_value={
                        "answer": "<!--SYS:SWITCH_TO_BUG-->",
                        "conversation_id": "conv-a-marker-failed",
                    }
                ),
            ),
        ):
            body = _post(
                "订单功能出现问题",
                sid,
                message_id="msg-marker-failed",
            )

        assert "尚未处理" in body["assistant_text"]
        assert router._store[sid]["state"]["conv_a"] == ""
        assert router._store[sid]["state"]["bug_v2_active"] is False
    finally:
        router._store.pop(sid, None)


def test_route_restore_resumes_bug_v2_after_process_restart() -> None:
    sid = "m2-h5-route-restore"
    fake = FakeBugOrchestrator(result=_submitted_result())
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(
                router,
                "_load_route_state",
                AsyncMock(
                    return_value={
                        "active": "A",
                        "conv_a": "conv-a-restored",
                        "conv_b": "",
                        "bug_v2_active": True,
                    }
                ),
            ),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as dify,
        ):
            result = asyncio.run(
                router.chat(
                    session_id=sid,
                    text="确认提交",
                    language="zh",
                    message_id="msg-restored",
                )
            )

        assert result["assistant_text"] == "反馈已记录，编号：rec-v2。"
        fake.message.assert_awaited_once()
        dify.assert_not_awaited()
    finally:
        router._store.pop(sid, None)


def test_off_mode_does_not_restore_legacy_b_route() -> None:
    sid = "m2-h5-off-legacy"
    fake = FakeBugOrchestrator(result=_ready_result())
    router._store.pop(sid, None)
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "off"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    return_value={
                        "answer": "旧 B 正常处理。",
                        "conversation_id": "conv-b-legacy",
                    }
                ),
            ) as dify,
        ):
            body = _post("订单结算失败", sid, message_id="msg-off")

        assert "尚未处理" in body["assistant_text"]
        fake.message.assert_not_awaited()
        dify.assert_not_awaited()
        assert router._store[sid]["state"]["active"] == "A"
        assert router._store[sid]["state"]["conv_b"] == ""
    finally:
        router._store.pop(sid, None)
