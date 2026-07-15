"""Pydantic models — health_consult 模块的请求/响应契约。

JSON 契约与 `frontend/src/data/*.ts` 严格对齐,
供 Agent 3 (前端) 和 Agent 1 (Dify) 共同遵守。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── Scenes & risk levels ───────────────────────────────────────
Scene = Literal["report", "symptom", "product", "chitchat"]
RiskLevel = Literal["low", "medium", "high", "urgent"]


# ── API responses ──────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class VersionResponse(BaseModel):
    version: str
    dify_workflow_id: str


# ── Question / Questionnaire ───────────────────────────────────
class QuestionOptionModel(BaseModel):
    key: str
    label: str
    weight: int = 0


class QuestionModel(BaseModel):
    id: str
    text: str
    type: str = "single"
    options: list[QuestionOptionModel]
    tag: str


class QuestionnaireResponse(BaseModel):
    id: str
    scene: Scene
    title: str
    description: str
    questions: list[QuestionModel]


# ── Solution ───────────────────────────────────────────────────
class SolutionSectionModel(BaseModel):
    icon: str
    title: str
    content: str


class SolutionResponse(BaseModel):
    id: str
    scene: Scene
    tag: str
    title: str
    riskLevel: RiskLevel
    department: str
    oneLineConclusion: str
    lifestyle: list[SolutionSectionModel]
    nutrition: list[SolutionSectionModel]
    alert: list[SolutionSectionModel]


# ── Scene / payload ────────────────────────────────────────────
class SceneResponse(BaseModel):
    scene: Scene
    risk_level: RiskLevel = "low"
    confidence: float = 1.0
    payload: dict[str, Any] = Field(default_factory=dict)
    # 原始 Dify 响应(可选,供前端调试)
    raw: Optional[dict[str, Any]] = None


# ── Chat request form (FastAPI Form params) ────────────────────
# Note: 文件通过 UploadFile 单独接收,不在 Pydantic 模型里。
class ChatRequestForm(BaseModel):
    """文档化表单字段,实际用 FastAPI Form() 在 endpoint 处接收。"""

    text: str = ""
    answers: str = ""  # JSON 字符串
    session_id: str = ""
    language: str = "中文"
