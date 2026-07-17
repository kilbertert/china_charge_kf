"""方案模板查询。

本模块是 `frontend/src/data/solutions.ts` 的 Python 等价镜像,
字段结构与 TS 版本严格一致,后端用于本地兜底。

数据来源:AI健康咨询模块场景GPT对话1.docx
  - 骨密度 6 种方案(P466-479)
  - 腿疼 6 种方案(P683-746)
"""

from __future__ import annotations

from typing import Optional, TypedDict

from .compliance_loader import get_config


class SolutionSection(TypedDict):
    icon: str
    title: str
    content: str


class Solution(TypedDict):
    id: str
    scene: str  # "report" | "symptom" | "product"
    tag: str
    title: str
    riskLevel: str  # "low" | "medium" | "high" | "urgent"
    department: str
    oneLineConclusion: str
    lifestyle: list[SolutionSection]
    nutrition: list[SolutionSection]
    alert: list[SolutionSection]


# ─── 场景一(骨密度)6 种方案 ────────────────────────────────
# ─── 方案 (单一事实源 shared/compliance.yaml) ──────────────────
_cfg = get_config()

# 按 scene 分组的 tag->solution (含 urgent_v1, 与前端一致)
BONE_DENSITY_SOLUTIONS: dict[str, Solution] = {
    s["tag"]: s for s in _cfg.list_solutions("report")
}  # type: ignore[assignment]
LEG_PAIN_SOLUTIONS: dict[str, Solution] = {
    s["tag"]: s for s in _cfg.list_solutions("symptom")
}  # type: ignore[assignment]

def get_solution(scene: str, tag: str) -> Optional[Solution]:
    """按 scene+tag 查询方案 (从 compliance.yaml)。"""
    return _cfg.get_solution(scene, tag)  # type: ignore[return-value]


def list_solutions(scene: str) -> list[Solution]:
    """返回某 scene 下全部方案 (从 compliance.yaml)。"""
    return _cfg.list_solutions(scene)  # type: ignore[return-value]
