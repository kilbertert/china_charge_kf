"""FastAPI app — charge_consult 模块。

端点(全部位于 /api/charge-consult 前缀下):
  POST /api/charge-consult/chat                    — 主入口,multipart/form-data
  GET  /api/charge-consult/danger-keywords         — 危险信号配置(5020 节点依赖)
  GET  /api/charge-consult/classify                — 4 维分类预览
  GET  /api/charge-consult/health                  — 健康检查
  GET  /api/charge-consult/version                 — 版本信息 + workflow_id
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .danger_signals import DANGER_SIGNALS_CONFIG, get_danger_signals
from .dify_proxy import chat_with_fallback
from .schemas import (
    CHARGE_ENDPOINT_ENUMS,
    CHARGE_REGION_ENUMS,
    ChargeSceneResponse,
    DangerSignalsConfig,
    HealthResponse,
    VersionResponse,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("charge_consult")


app = FastAPI(
    title="AI Charge Consult",
    version=settings.app_version,
    docs_url="/api/charge-consult/docs",
    openapi_url="/api/charge-consult/openapi.json",
    redoc_url="/api/charge-consult/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/charge-consult/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@app.get("/api/charge-consult/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    return VersionResponse(
        version=settings.app_version,
        dify_workflow_id=settings.dify_workflow_id,
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


# ── 危险信号配置(SPEC-D2 5020 节点依赖) ─────────────────────
@app.get(
    "/api/charge-consult/danger-keywords",
    response_model=DangerSignalsConfig,
)
async def list_danger_keywords(
    endpoint: Optional[str] = Query(
        default=None,
        description="按端类型过滤, user/butler/pc, 空=全部",
    ),
) -> DangerSignalsConfig:
    """返回当前生效的危险信号配置。

    5020 code 节点会调用本接口获取关键词。
    """
    if endpoint and endpoint not in CHARGE_ENDPOINT_ENUMS:
        raise HTTPException(
            status_code=400,
            detail=f"endpoint must be one of {list(CHARGE_ENDPOINT_ENUMS)}",
        )

    if endpoint:
        signals = get_danger_signals(endpoint)
        cfg = DangerSignalsConfig(
            signals=signals,
            last_updated=DANGER_SIGNALS_CONFIG.last_updated,
            version=DANGER_SIGNALS_CONFIG.version,
        )
        return cfg

    return DANGER_SIGNALS_CONFIG


# ── 4 维分类预览(SPEC-B1 5002-1 节点的备选) ─────────────────
@app.get("/api/charge-consult/classify")
async def classify_preview(
    text: str = Query(..., min_length=1, max_length=4000),
    language: str = Query(default="zh"),
    hint_endpoint: Optional[str] = Query(default=None),
    hint_region: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    """本地 4 维分类预览 — 不调用 Dify,仅做关键词判定。"""
    from .scene_router import classify_4d
    scene, endpoint, region, pile_type, conf = classify_4d(
        text=text, language=language, hint_endpoint=hint_endpoint, hint_region=hint_region
    )
    return {
        "scene": scene,
        "endpoint": endpoint,
        "region": region,
        "pile_type": pile_type,
        "confidence": conf,
    }


# ── 主入口: POST /api/charge-consult/chat ─────────────────────
@app.post(
    "/api/charge-consult/chat",
    response_model=ChargeSceneResponse,
)
async def chat(
    text: str = Form(default="", max_length=4000),
    answers: str = Form(default=""),
    session_id: str = Form(default=""),
    turn: int = Form(default=1, ge=1, le=20),
    language: str = Form(default="zh"),
    hint_endpoint: Optional[str] = Form(default=None),
    hint_region: Optional[str] = Form(default=None),
    files: Optional[list[UploadFile]] = File(default=None),
) -> ChargeSceneResponse:
    """主入口 — 接收 multipart/form-data,调用 Dify workflow,失败时本地兜底。

    返回 ChargeSceneResponse(SPEC-A1 4 维分类契约)。
    """
    sid = session_id or str(uuid.uuid4())

    if hint_endpoint and hint_endpoint not in CHARGE_ENDPOINT_ENUMS:
        raise HTTPException(
            status_code=400,
            detail=f"hint_endpoint must be one of {list(CHARGE_ENDPOINT_ENUMS)}",
        )
    if hint_region and hint_region not in CHARGE_REGION_ENUMS:
        raise HTTPException(
            status_code=400,
            detail=f"hint_region must be one of {list(CHARGE_REGION_ENUMS)}",
        )
    if language not in ("zh", "en", "vi"):
        raise HTTPException(status_code=400, detail="language must be zh/en/vi")

    inputs: dict[str, Any] = {
        "input_text": text,
        "input_session_id": sid,
        "input_turn": turn,
        "input_language": language,
    }
    if hint_endpoint:
        inputs["input_hint_endpoint"] = hint_endpoint
    if hint_region:
        inputs["input_hint_region"] = hint_region
    if answers:
        try:
            json.loads(answers)
            inputs["input_answers"] = answers
        except (ValueError, TypeError) as e:
            log.warning("answers JSON invalid: %s", e)
            inputs["input_answers"] = ""

    file_count = len(files) if files else 0
    if file_count > 0:
        log.info("received %d file(s), MVP暂不上传 Dify", file_count)
        inputs["input_file_count"] = str(file_count)

    parsed, source = await chat_with_fallback(
        text=text,
        language=language,
        session_id=sid,
        hint_endpoint=hint_endpoint,
        hint_region=hint_region,
        inputs=inputs,
    )

    if source == "local_fallback":
        response = ChargeSceneResponse.model_validate(parsed)
        log.info(
            "chat source=local_fallback scene=%s confidence=%.2f",
            response.scene, response.confidence,
        )
        return response

    if "source" not in parsed:
        parsed["source"] = "dify"
    if "ts" not in parsed:
        parsed["ts"] = datetime.now(timezone.utc).isoformat()
    if "endpoint" not in parsed:
        parsed["endpoint"] = hint_endpoint or "user"
    if "region" not in parsed:
        parsed["region"] = hint_region or ("overseas" if language == "en" else "cn")
    if "pile_type" not in parsed:
        parsed["pile_type"] = "public"
    if "risk_level" not in parsed:
        parsed["risk_level"] = "low"
    if "confidence" not in parsed:
        parsed["confidence"] = 0.9

    try:
        response = ChargeSceneResponse.model_validate(parsed)
    except Exception as e:
        log.warning("Dify output not match schema, fallback: %s", e)
        from .scene_router import build_local_fallback
        response = build_local_fallback(
            text=text, language=language,
            hint_endpoint=hint_endpoint, hint_region=hint_region,
        )

    return response
