from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    """A single media attachment embedded in an assistant reply.

    `type` drives frontend rendering: ``image`` → ``<img>``, ``video`` → ``<video>``.
    `url` MUST be an http(s) URL; the parser in response_parser enforces this
    to defend against javascript:/data: scheme injection.
    """

    type: Literal["image", "video"]
    url: str
    description: Optional[str] = None


class ChatResponse(BaseModel):
    """对外响应结构 — 与 app/schemas.py 同形,前端可零改动切换。"""

    assistant_text: str = Field(..., description="Final answer text from Dify workflow")
    image_id: Optional[str] = Field(default=None, description="Uploaded image upload_file_id (if any)")
    audio_id: Optional[str] = Field(default=None, description="Uploaded audio upload_file_id (if any)")
    media: list[MediaItem] = Field(
        default_factory=list,
        description=(
            "Media attachments the assistant wants to show alongside the text. "
            "Source: structured JSON output of the Dify workflow, with a regex "
            "fallback that scans assistant_text for image/video URLs."
        ),
    )
    raw: Optional[dict] = Field(default=None, description="Raw workflow response (optional)")
