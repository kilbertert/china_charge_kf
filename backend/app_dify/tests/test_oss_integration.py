"""End-to-end test for OSS-hosted image replies.

This test mocks the Dify workflow response (no real Dify API call) and
exercises the FastAPI endpoint to confirm that the assistant's ``media[]``
field carries the OSS image URL all the way through to the HTTP response,
exactly the way the H5 frontend expects to receive it.

The OSS URL asserted here is the row-#20 entry in ``kb-assets/KB-CHARGE-PILE.md``
(``pc-backend-billing-template-domestic-four-wheel-1.png``). The test query
"如何给充电桩设置阶梯电价" is the same query listed in the Dify retrieval
acceptance test in Step 3 of the runbook.

Run from the ``backend/`` directory::

    cd backend && python -m pytest app_dify/tests/test_oss_integration.py -q
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app_dify.main import app

# Row #20 in kb-assets/MANIFEST.md / KB-CHARGE-PILE.md
EXPECTED_OSS_URL = (
    "https://trendpower-ai-customer-service.oss-cn-guangzhou.aliyuncs.com/"
    "kb/charge-pile/pc-backend-billing-template-domestic-four-wheel-1.png"
)


def _make_fake_workflow_response(
    text: str = "请按以下步骤设置阶梯电价：进入 PC 管理后端 → 计费模板 → 新建模板 → 选择国内四轮 → 设置峰平谷电价。",
    media: list[dict] | None = None,
) -> dict:
    """Build a Dify-style workflow blocking response with a {text, media} JSON
    payload encoded in the ``output`` variable. The response parser in
    ``app_dify.response_parser`` unpacks this into ``ChatResponse.media``.
    """
    if media is None:
        media = [
            {
                "type": "image",
                "url": EXPECTED_OSS_URL,
                "description": "阶梯电价模板设置入口",
            }
        ]
    payload = {"text": text, "media": media}
    return {
        "data": {
            "outputs": {
                "output": json.dumps(payload, ensure_ascii=False),
            }
        }
    }


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_chat_returns_oss_media_url_for_billing_template_query(client: TestClient) -> None:
    """A query about tiered pricing must return the billing template image
    exactly as the KB-CHARGE-PILE.md describes it."""
    fake_raw = _make_fake_workflow_response()

    with patch("app_dify.main.DifyClient") as MockClient:
        MockClient.return_value.run_workflow = AsyncMock(return_value=fake_raw)

        resp = client.post(
            "/api/chat",
            data={"text": "如何给充电桩设置阶梯电价", "language": "中文"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Sanity: the assistant text from the workflow is passed through
    assert "阶梯电价" in body["assistant_text"]

    # The media[] field is the contract this test exists to assert.
    media = body["media"]
    assert isinstance(media, list)
    assert len(media) == 1
    item = media[0]
    assert item["type"] == "image"
    assert item["url"] == EXPECTED_OSS_URL
    assert item["description"] == "阶梯电价模板设置入口"


def test_chat_returns_empty_media_when_payload_omits_it(client: TestClient) -> None:
    """If the workflow's payload has no media, the response.media must be []."""
    fake_raw = _make_fake_workflow_response(
        text="您好，我还在学习中。",
        media=[],
    )

    with patch("app_dify.main.DifyClient") as MockClient:
        MockClient.return_value.run_workflow = AsyncMock(return_value=fake_raw)

        resp = client.post(
            "/api/chat",
            data={"text": "你好", "language": "中文"},
        )

    assert resp.status_code == 200
    assert resp.json()["media"] == []


def test_chat_strips_unsafe_media_url(client: TestClient) -> None:
    """Defense-in-depth: even if the LLM emits a ``javascript:`` URL,
    ``_normalize_media_item`` must drop it. The frontend never sees it."""
    fake_raw = _make_fake_workflow_response(
        media=[
            {"type": "image", "url": "javascript:alert(1)", "description": "xss"},
            {"type": "image", "url": EXPECTED_OSS_URL, "description": "ok"},
        ]
    )

    with patch("app_dify.main.DifyClient") as MockClient:
        MockClient.return_value.run_workflow = AsyncMock(return_value=fake_raw)

        resp = client.post(
            "/api/chat",
            data={"text": "test", "language": "中文"},
        )

    assert resp.status_code == 200
    media_urls = [m["url"] for m in resp.json()["media"]]
    assert EXPECTED_OSS_URL in media_urls
    assert not any(u.startswith("javascript:") for u in media_urls)
