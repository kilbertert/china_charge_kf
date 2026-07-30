"""H5 图片上传契约回归：真实图片透传，坏图/下游失败不得静默降级为纯文本。"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app_dify.bug_orchestrator_client import BugOrchestratorError
from app_dify.config import settings
from app_dify.dify_client import DifyClient, DifyError
from app_dify.main import app, router

client = TestClient(app)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image-payload"


class FakeBugOrchestrator:
    enabled = True

    def __init__(self, *, result=None, side_effect=None) -> None:
        self.message = AsyncMock(return_value=result, side_effect=side_effect)


def test_invalid_image_is_rejected_before_dify() -> None:
    with patch.object(DifyClient, "run_chatflow", AsyncMock()) as run:
        resp = client.post(
            "/api/chat",
            data={"text": "请看截图", "session_id": "test-invalid-image"},
            files={"image": ("fake.jpg", b"not-an-image", "image/jpeg")},
        )

    assert resp.status_code == 400
    assert "图片格式无效" in resp.json()["detail"]
    run.assert_not_awaited()


def test_dify_image_failure_is_visible_and_never_retried_without_file() -> None:
    sid = "test-image-dify-error"
    try:
        with (
            patch.object(
                DifyClient, "upload_file", AsyncMock(return_value="upload-image-1")
            ),
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    side_effect=DifyError("Dify chatflow HTTP error: 400 vision failed")
                ),
            ) as run,
        ):
            resp = client.post(
                "/api/chat",
                data={"text": "请分析这张产品图片", "session_id": sid},
                files={"image": ("screen.png", PNG_BYTES, "image/png")},
            )

        assert resp.status_code == 502
        assert resp.json()["detail"].startswith("图片处理失败")
        assert "vision failed" not in resp.text
        assert run.await_count == 1, "带图失败后不得移除 files 再调用一次"
        assert run.await_args.kwargs["files"][0]["type"] == "image"
    finally:
        router._store.pop(sid, None)


def test_obvious_bug_image_goes_directly_to_v2_without_dify_upload() -> None:
    sid = "test-image-cross-app"
    fake = FakeBugOrchestrator(
        result={
            "success": True,
            "assistant_text": "请确认反馈。",
            "state": "ready_to_submit",
            "continue_session": True,
            "fallback_required": False,
        }
    )
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "upload_file", AsyncMock()) as upload,
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as run,
        ):
            resp = client.post(
                "/api/chat",
                data={"text": "这个页面有问题", "session_id": sid},
                files={"image": ("screen.png", PNG_BYTES, "image/png")},
            )

        assert resp.status_code == 200
        assert resp.json()["assistant_text"] == "请确认反馈。"
        fake.message.assert_awaited_once()
        assert fake.message.await_args.kwargs["image_bytes"] == PNG_BYTES
        upload.assert_not_awaited()
        run.assert_not_awaited()
    finally:
        router._store.pop(sid, None)


def test_bug_v2_image_failure_is_visible_without_dify_fallback() -> None:
    sid = "test-image-cache-failure"
    fake = FakeBugOrchestrator(side_effect=BugOrchestratorError("timeout"))
    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "upload_file", AsyncMock()) as upload,
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as run,
        ):
            resp = client.post(
                "/api/chat",
                data={"text": "这个页面有问题", "session_id": sid},
                files={"image": ("screen.png", PNG_BYTES, "image/png")},
            )

        assert resp.status_code == 200
        assert "尚未处理" in resp.json()["assistant_text"]
        upload.assert_not_awaited()
        run.assert_not_awaited()
    finally:
        router._store.pop(sid, None)


def test_historical_b_state_with_active_v2_sends_confirmation_to_orchestrator() -> None:
    sid = "test-image-confirmation-order"
    router._store[sid] = {
        "state": {
            "active": "B",
            "conv_a": "conv-a",
            "conv_b": "conv-b-existing",
            "bug_v2_active": True,
        },
        "ts": time.monotonic(),
    }
    fake = FakeBugOrchestrator(
        result={
            "success": True,
            "assistant_text": "已记录。",
            "state": "submitted",
            "continue_session": False,
            "fallback_required": False,
        }
    )

    try:
        with (
            patch.object(settings, "bugtrack_orchestrator_mode", "active"),
            patch.object(router, "_bug_orchestrator", fake),
            patch.object(router, "_save_route_state", AsyncMock(return_value=True)),
            patch.object(DifyClient, "upload_file", AsyncMock()) as upload,
            patch.object(DifyClient, "run_chatflow", AsyncMock()) as run,
        ):
            resp = client.post(
                "/api/chat",
                data={"text": "确认记录，并附上这张图", "session_id": sid},
                files={"image": ("confirm.png", PNG_BYTES, "image/png")},
            )

        assert resp.status_code == 200
        assert resp.json()["assistant_text"] == "已记录。"
        fake.message.assert_awaited_once()
        assert fake.message.await_args.kwargs["image_bytes"] == PNG_BYTES
        upload.assert_not_awaited()
        run.assert_not_awaited()
        state = router._store[sid]["state"]
        assert state["active"] == "A"
        assert state["conv_b"] == ""
    finally:
        router._store.pop(sid, None)
