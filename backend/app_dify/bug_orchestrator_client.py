"""HTTP client for the active Bug assistant v2 service."""

from __future__ import annotations

from typing import Any

import httpx


class BugOrchestratorError(RuntimeError):
    pass


class BugOrchestratorClient:
    def __init__(self, api_base: str, timeout: float = 45.0) -> None:
        self._api_base = (api_base or "").rstrip("/")
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self._api_base)

    async def message(
        self,
        *,
        text: str,
        session_id: str,
        language: str = "",
        message_id: str = "",
        image_bytes: bytes | None = None,
        image_name: str = "",
        image_mime: str = "",
        event: str = "",
    ) -> dict[str, Any]:
        if not self._api_base:
            raise BugOrchestratorError("Bug orchestrator API is not configured")
        data = {
            "text": text,
            "session_id": session_id,
            "channel": "h5",
            "user_key": session_id,
            "language": language,
            "message_id": message_id,
            "event": event,
        }
        files = None
        if image_bytes:
            files = {
                "image": (
                    image_name or "bug-screenshot.png",
                    image_bytes,
                    image_mime or "application/octet-stream",
                )
            }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout)
            ) as client:
                response = await client.post(
                    f"{self._api_base}/internal/bugtrack/v2/message",
                    data=data,
                    files=files,
                )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BugOrchestratorError(str(exc)) from exc
        if not isinstance(body, dict) or not body.get("success"):
            error = (body or {}).get("error") if isinstance(body, dict) else ""
            raise BugOrchestratorError(str(error or "invalid response"))
        return body

    async def notifications(
        self, *, session_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not self._api_base:
            raise BugOrchestratorError("Bug orchestrator API is not configured")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout)
            ) as client:
                response = await client.get(
                    f"{self._api_base}/internal/bugtrack/v2/notifications",
                    params={
                        "channel": "h5",
                        "user_key": session_id,
                        "session_id": session_id,
                        "limit": max(1, min(limit, 100)),
                    },
                )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BugOrchestratorError(str(exc)) from exc
        if not isinstance(body, dict) or not body.get("success"):
            raise BugOrchestratorError("invalid notification response")
        notifications = body.get("notifications", [])
        if not isinstance(notifications, list):
            raise BugOrchestratorError("invalid notification response")
        return [item for item in notifications if isinstance(item, dict)]

    async def progress(self, *, session_id: str) -> dict[str, Any]:
        if not self._api_base:
            raise BugOrchestratorError("Bug orchestrator API is not configured")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client:
                response = await client.get(
                    f"{self._api_base}/internal/bugtrack/v2/progress",
                    params={"channel": "h5", "user_key": session_id, "session_id": session_id},
                )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BugOrchestratorError(str(exc)) from exc
        if not isinstance(body, dict) or not body.get("success"):
            raise BugOrchestratorError("invalid progress response")
        return body

    async def acknowledge_notifications(
        self, *, session_id: str, notification_ids: list[str]
    ) -> int:
        if not self._api_base:
            raise BugOrchestratorError("Bug orchestrator API is not configured")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout)
            ) as client:
                response = await client.post(
                    f"{self._api_base}/internal/bugtrack/v2/notifications/ack",
                    json={
                        "channel": "h5",
                        "user_key": session_id,
                        "session_id": session_id,
                        "notification_ids": notification_ids,
                    },
                )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BugOrchestratorError(str(exc)) from exc
        if not isinstance(body, dict) or not body.get("success"):
            raise BugOrchestratorError("invalid notification acknowledgement")
        acknowledged = body.get("acknowledged", 0)
        if (
            isinstance(acknowledged, bool)
            or not isinstance(acknowledged, int)
            or acknowledged < 0
        ):
            raise BugOrchestratorError("invalid notification acknowledgement")
        return acknowledged


__all__ = ["BugOrchestratorClient", "BugOrchestratorError"]
