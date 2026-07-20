"""H5 图片上传契约回归：真实图片透传，坏图/下游失败不得静默降级为纯文本。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app_dify.dify_client import DifyClient, DifyError
from app_dify.main import app, router


client = TestClient(app)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image-payload"


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
                AsyncMock(side_effect=DifyError("Dify chatflow HTTP error: 400 vision failed")),
            ) as run,
        ):
            resp = client.post(
                "/api/chat",
                data={"text": "请看截图", "session_id": sid},
                files={"image": ("screen.png", PNG_BYTES, "image/png")},
            )

        assert resp.status_code == 502
        assert resp.json()["detail"].startswith("图片处理失败")
        assert "vision failed" not in resp.text
        assert run.await_count == 1, "带图失败后不得移除 files 再调用一次"
        assert run.await_args.kwargs["files"][0]["type"] == "image"
    finally:
        router._store.pop(sid, None)


def test_image_is_reuploaded_when_router_switches_from_a_to_b() -> None:
    sid = "test-image-cross-app"
    old_dual = router._dual
    old_client_b = router._client_b
    router._dual = True
    router._client_b = DifyClient("http://dify.test/v1", "app-test-b", "test-user")
    try:
        with (
            patch.object(
                DifyClient,
                "upload_file",
                AsyncMock(side_effect=["upload-a", "upload-b"]),
            ) as upload,
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    side_effect=[
                        {
                            "answer": "<!--SYS:SWITCH_TO_BUG-->",
                            "conversation_id": "conv-a",
                        },
                        {"answer": "已读取截图。", "conversation_id": "conv-b"},
                    ]
                ),
            ) as run,
            patch.object(
                router,
                "_cache_bug_image",
                AsyncMock(return_value=True),
            ) as cache,
        ):
            resp = client.post(
                "/api/chat",
                data={"text": "这个页面有问题", "session_id": sid},
                files={"image": ("screen.png", PNG_BYTES, "image/png")},
            )

        assert resp.status_code == 200
        assert resp.json()["assistant_text"] == "已读取截图。"
        assert upload.await_count == 2
        assert run.await_count == 2
        assert run.await_args_list[0].kwargs["files"][0]["upload_file_id"] == "upload-a"
        assert run.await_args_list[1].kwargs["files"][0]["upload_file_id"] == "upload-b"
        cache.assert_awaited_once_with("conv-b", PNG_BYTES, "screen.png")
    finally:
        router._store.pop(sid, None)
        router._dual = old_dual
        router._client_b = old_client_b


def test_bug_image_cache_failure_is_visible_to_user() -> None:
    sid = "test-image-cache-failure"
    old_dual = router._dual
    old_client_b = router._client_b
    router._dual = True
    router._client_b = DifyClient("http://dify.test/v1", "app-test-b", "test-user")
    try:
        with (
            patch.object(
                DifyClient,
                "upload_file",
                AsyncMock(side_effect=["upload-a", "upload-b"]),
            ),
            patch.object(
                DifyClient,
                "run_chatflow",
                AsyncMock(
                    side_effect=[
                        {
                            "answer": "<!--SYS:SWITCH_TO_BUG-->",
                            "conversation_id": "conv-a",
                        },
                        {"answer": "请确认反馈。", "conversation_id": "conv-b"},
                    ]
                ),
            ),
            patch.object(
                router,
                "_cache_bug_image",
                AsyncMock(return_value=False),
            ),
        ):
            resp = client.post(
                "/api/chat",
                data={"text": "这个页面有问题", "session_id": sid},
                files={"image": ("screen.png", PNG_BYTES, "image/png")},
            )

        assert resp.status_code == 200
        assert "截图暂未保存成功" in resp.json()["assistant_text"]
    finally:
        router._store.pop(sid, None)
        router._dual = old_dual
        router._client_b = old_client_b
