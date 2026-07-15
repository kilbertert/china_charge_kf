"""FastAPI app — health_consult 模块。

端点(全部位于 /api/health-consult 前缀下):
  POST /api/health-consult/chat              — 主入口
  GET  /api/health-consult/questionnaire/{id} — 拉取量表
  GET  /api/health-consult/solution/{scene}/{tag} — 拉取方案
  GET  /api/health-consult/health            — 健康检查
  GET  /api/health-consult/version           — 版本信息
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .dify_proxy import DifyProxyError, chat_with_dify
from .questionnaire import get_questionnaire
from .schemas import (
    HealthResponse,
    QuestionnaireResponse,
    SceneResponse,
    SolutionResponse,
    VersionResponse,
)
from .scene_router import get_default_scene_response
from .solutions import get_solution


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("health_consult")


app = FastAPI(
    title="AI Health Consult",
    version=settings.app_version,
    docs_url="/api/health-consult/docs",
    openapi_url="/api/health-consult/openapi.json",
    redoc_url="/api/health-consult/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health-consult/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@app.get("/api/health-consult/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    return VersionResponse(
        version=settings.app_version,
        dify_workflow_id=settings.dify_workflow_id,
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/health-consult/chat", response_model=SceneResponse)
async def chat(
    text: str = Form(""),
    files: Optional[list[UploadFile]] = File(default=None),
    answers: str = Form(""),
    session_id: str = Form(""),
    language: str = Form("中文"),
) -> SceneResponse:
    """主入口 — 接收 multipart/form-data,转发 Dify,失败时本地兜底。"""
    sid = session_id or str(uuid.uuid4())

    answers_dict: dict[str, Any] = {}
    if answers:
        try:
            parsed = json.loads(answers)
            if isinstance(parsed, dict):
                answers_dict = parsed
        except (ValueError, TypeError) as e:
            log.warning("answers JSON parse failed: %s", e)
            raise HTTPException(status_code=400, detail=f"answers not valid JSON: {e}")

    try:
        result = await chat_with_dify(
            text=text,
            files=files or [],
            answers=answers_dict,
            session_id=sid,
            language=language,
        )
        return SceneResponse(**result)
    except DifyProxyError as e:
        log.warning("Dify proxy failed, falling back to local router: %s", e)
        fallback = get_default_scene_response(text=text, answers=answers_dict)
        return SceneResponse(**fallback)


@app.get(
    "/api/health-consult/questionnaire/{questionnaire_id}",
    response_model=QuestionnaireResponse,
)
async def get_questionnaire_endpoint(questionnaire_id: str) -> QuestionnaireResponse:
    q = get_questionnaire(questionnaire_id)
    if q is None:
        raise HTTPException(status_code=404, detail=f"questionnaire not found: {questionnaire_id}")
    return QuestionnaireResponse(**q)


@app.get(
    "/api/health-consult/solution/{scene}/{tag}",
    response_model=SolutionResponse,
)
async def get_solution_endpoint(scene: str, tag: str) -> SolutionResponse:
    s = get_solution(scene, tag)
    if s is None:
        raise HTTPException(status_code=404, detail=f"solution not found: scene={scene} tag={tag}")
    return SolutionResponse(**s)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "health_consult.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=False,
    )
