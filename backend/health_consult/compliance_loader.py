"""健康合规规则单一事实源加载器。

从 shared/compliance.yaml 加载场景关键词/危险信号/正则/量表/风险映射/阈值/方案,
供 scene_router / questionnaire / solutions 共享, 消除前后端 4 份重复数据。

路径搜索 (按顺序):
  1. COMPLIANCE_YAML_PATH 环境变量 (显式覆盖, 测试/部署用)
  2. /app/shared/compliance.yaml (容器, Dockerfile COPY shared/ /app/shared/)
  3. <项目根>/shared/compliance.yaml (本地开发)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

_SCENE_NAMES = ("chitchat", "report", "symptom", "product")


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get("COMPLIANCE_YAML_PATH")
    if env_path:
        paths.append(Path(env_path))
    paths.append(Path("/app/shared/compliance.yaml"))
    paths.append(Path(__file__).resolve().parents[2] / "shared" / "compliance.yaml")
    return paths


def _find_yaml() -> Path:
    for p in _candidate_paths():
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"compliance.yaml 未找到, 搜索路径: {[str(p) for p in _candidate_paths()]}"
    )


class ComplianceConfig:
    """合规规则配置 (从 YAML 加载的不可变视图)。"""

    def __init__(self, data: dict[str, Any]) -> None:
        scenes = data.get("scenes") or {}
        self._scenes: dict[str, dict] = {k: scenes.get(k) or {} for k in _SCENE_NAMES}
        self.urgent_phrases: tuple[str, ...] = tuple(scenes.get("urgent_phrases") or [])
        self.regexes: dict[str, str] = scenes.get("regexes") or {}
        self.risk_mapping: dict[str, str] = scenes.get("risk_mapping") or {}

        self._questionnaires: dict[str, dict] = {
            q["id"]: q for q in (data.get("questionnaires") or []) if "id" in q
        }
        self.tag_risk_maps: dict[str, dict[str, str]] = data.get("tag_risk_maps") or {}
        self.thresholds: dict[str, dict[str, Any]] = data.get("classification_thresholds") or {}

        self._solutions: list[dict] = list(data.get("solutions") or [])
        self._solutions_by_key: dict[tuple[str, str], dict] = {
            (s["scene"], s["tag"]): s
            for s in self._solutions
            if "scene" in s and "tag" in s
        }

    # ── scenes ──────────────────────────────────────────────
    def keywords(self, scene: str) -> tuple[str, ...]:
        return tuple(self._scenes.get(scene, {}).get("keywords") or [])

    def regex_pattern(self, name: str) -> str:
        return self.regexes.get(name, "")

    def risk_for_scene(self, scene: str) -> str:
        return self.risk_mapping.get(scene, "low")

    # ── questionnaires ──────────────────────────────────────
    def get_questionnaire(self, qid: str) -> dict:
        return self._questionnaires.get(qid, {})

    def questionnaires(self) -> list[dict]:
        return list(self._questionnaires.values())

    # ── tag_risk_maps / thresholds ──────────────────────────
    def tag_risk_map(self, name: str) -> dict[str, str]:
        return self.tag_risk_maps.get(name, {})

    def threshold(self, group: str, key: str, default: Any = None) -> Any:
        return (self.thresholds.get(group) or {}).get(key, default)

    # ── solutions ───────────────────────────────────────────
    def get_solution(self, scene: str, tag: str) -> Optional[dict]:
        return self._solutions_by_key.get((scene, tag))

    def list_solutions(self, scene: Optional[str] = None) -> list[dict]:
        if scene is None:
            return list(self._solutions)
        return [s for s in self._solutions if s.get("scene") == scene]


@lru_cache(maxsize=1)
def _load_cached() -> ComplianceConfig:
    path = _find_yaml()
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return ComplianceConfig(data)


def get_config() -> ComplianceConfig:
    """返回单例 ComplianceConfig (首次调用加载 YAML, fail-fast)。"""
    return _load_cached()


def reload() -> ComplianceConfig:
    """清除缓存重新加载 (测试用)。"""
    _load_cached.cache_clear()
    return get_config()
