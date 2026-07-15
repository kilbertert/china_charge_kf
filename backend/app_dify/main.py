from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app_dify.config import settings
from app_dify.dify_client import DifyClient, DifyError
from app_dify.response_parser import extract_assistant_text_and_media
from app_dify.schemas import ChatResponse, MediaItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("app_dify")

app = FastAPI(
    title="China Charge - Dify H5 Chat Backend",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "backend": "dify",
        "api_base": settings.dify_api_base,
        "end_user": settings.dify_end_user,
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


def _sniff_audio_type(filename: str, declared: str | None) -> str:
    """Normalize audio MIME type for Dify upload (Dify accepts wav/mp3/m4a/webm)."""
    name = (filename or "").lower()
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".mp3"):
        return "audio/mpeg"
    if name.endswith(".m4a"):
        return "audio/mp4"
    if name.endswith(".webm"):
        return "audio/webm"
    if name.endswith(".ogg") or name.endswith(".oga"):
        return "audio/ogg"
    if name.endswith(".mp4"):
        return "audio/mp4"
    return declared or "audio/wav"


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    text: str = Form(""),
    image: Optional[UploadFile] = File(default=None),
    audio: Optional[UploadFile] = File(default=None),
    language: str = Form("中文"),
) -> ChatResponse:
    client = DifyClient(
        api_base=settings.dify_api_base,
        api_key=settings.dify_api_key,
        end_user=settings.dify_end_user,
    )

    image_id: Optional[str] = None
    if image is not None:
        content = await image.read()
        if content:
            try:
                image_id = await client.upload_file(
                    filename=image.filename or "image",
                    content=content,
                    content_type=image.content_type or "image/jpeg",
                )
                log.info("Uploaded image to Dify: file_id=%s size=%d", image_id, len(content))
            except DifyError as e:
                return ChatResponse(
                    assistant_text=f"[DifyError:image_upload] {e}",
                    image_id=None,
                    audio_id=None,
                    raw=None,
                )

    audio_id: Optional[str] = None
    if audio is not None:
        content = await audio.read()
        if content:
            ctype = _sniff_audio_type(audio.filename or "", audio.content_type)
            try:
                audio_id = await client.upload_file(
                    filename=audio.filename or "audio.wav",
                    content=content,
                    content_type=ctype,
                )
                log.info(
                    "Uploaded audio to Dify: file_id=%s size=%d ctype=%s",
                    audio_id, len(content), ctype,
                )
            except DifyError as e:
                return ChatResponse(
                    assistant_text=f"[DifyError:audio_upload] {e}",
                    image_id=image_id,
                    audio_id=None,
                    raw=None,
                )

    # ---- Build workflow inputs ----
    # Dify workflow 文件型输入必须是数组,即使只有一个文件
    inputs: dict = {
        settings.dify_input_text: text or "",
        settings.dify_input_language: language,
    }
    if image_id:
        inputs[settings.dify_input_image] = [client.file_ref(image_id, "image")]
    if audio_id:
        inputs[settings.dify_input_audio] = [client.file_ref(audio_id, "audio")]

    log.info("Dify workflow inputs keys=%s", list(inputs.keys()))

    # ---- Run workflow ----
    try:
        raw = await client.run_workflow(inputs=inputs, response_mode="blocking")
    except DifyError as e:
        log.error("Dify workflow error: %s", e)
        return ChatResponse(
            assistant_text=f"[DifyError:workflow] {e}",
            image_id=image_id,
            audio_id=audio_id,
            raw=None,
        )

    assistant_text, media = extract_assistant_text_and_media(
        raw, preferred_key=settings.dify_output_text
    )
    return ChatResponse(
        assistant_text=assistant_text,
        image_id=image_id,
        audio_id=audio_id,
        media=[MediaItem(**m) for m in media],
        raw=raw,
    )
