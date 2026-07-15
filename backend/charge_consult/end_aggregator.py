"""End 节点聚合 — SPEC-E1,5081 code 节点的 Python 实现。

5081 code 节点在 Dify yml 里的核心工作:
  1. 接收 4 路(scene A/B/C/D/E) + 后台三流的输出
  2. 组装成完整的 ChargeSceneResponse(SPEC-A1 契约)
  3. 序列化为 JSON 字符串
  4. 输出给 5099 end 节点

本模块提供 Python 实现,可用于:
  - 后端兜底路径(本地 fallback)
  - 单元测试(SPEC-H1 冒烟)
  - 后续 Dify yml 部署前的 dry-run 验证
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from charge_consult.schemas import (
    CHARGE_SCENE_ENUMS,
    ChargeDangerSignalHit,
    ChargeEndpoint,
    ChargeFaqHit,
    ChargePayload,
    ChargePileType,
    ChargeRegion,
    ChargeRiskLevel,
    ChargeScene,
    ChargeSceneResponse,
    NextAction,
)


# ── 主聚合函数 ────────────────────────────────────────────────
def aggregate_scene_response(
    scene: str,
    endpoint: str = "user",
    region: str = "cn",
    pile_type: str = "public",
    risk_level: str = "low",
    confidence: float = 1.0,
    payload: Optional[dict[str, Any]] = None,
    raw: Optional[dict[str, Any]] = None,
    source: str = "dify",
    ts: Optional[str] = None,
) -> ChargeSceneResponse:
    """从 Dify 5081 节点的输入聚合 ChargeSceneResponse。

    5081 节点在 yml 里的典型工作:
        inputs = {
            "scene": <5002-1 output.scene>,
            "endpoint": <5002-1 output.endpoint>,
            ...
            "payload": <path_x output>,
        }
        output = aggregate_scene_response(**inputs).model_dump_json()

    Args:
        scene: 业务意图
        endpoint: 端类型
        region: 地域
        pile_type: 桩型
        risk_level: 风险等级
        confidence: 置信度 0-1
        payload: dict 形式(由各路径处理器 build_*_payload 返回)
        raw: 原始 Dify 响应(可选)
        source: "dify" / "local_fallback" / "hybrid"
        ts: ISO8601 时间戳(默认当前 UTC)

    Returns:
        ChargeSceneResponse: 严格符合 SPEC-A1 契约的对象
    """
    # 校验 scene 枚举
    if scene not in CHARGE_SCENE_ENUMS:
        scene = "fallback"
        confidence = min(confidence, 0.3)

    # 构造 payload(Pydantic 校验)
    if payload is None:
        payload_dict: dict[str, Any] = {"text": ""}
    elif isinstance(payload, ChargePayload):
        payload_dict = payload.model_dump(mode="json")
    else:
        payload_dict = payload

    cp = ChargePayload.model_validate(payload_dict)

    return ChargeSceneResponse(
        scene=scene,  # type: ignore[arg-type]
        endpoint=endpoint,  # type: ignore[arg-type]
        region=region,  # type: ignore[arg-type]
        pile_type=pile_type,  # type: ignore[arg-type]
        risk_level=risk_level,  # type: ignore[arg-type]
        confidence=confidence,
        payload=cp,
        raw=raw,
        source=source,  # type: ignore[arg-type]
        ts=ts or datetime.now(timezone.utc).isoformat(),
    )


# ── 便捷函数:从 Dify inputs dict 直接聚合 ───────────────────
def aggregate_from_dify_inputs(
    inputs: dict[str, Any],
    raw: Optional[dict[str, Any]] = None,
) -> ChargeSceneResponse:
    """从 Dify 5081 节点的 inputs dict 聚合。

    这是 yml 节点最常用的入口,把所有 variable-aggregator 输出
    聚合成一个对象。
    """
    return aggregate_scene_response(
        scene=inputs.get("scene", "fallback"),
        endpoint=inputs.get("endpoint", "user"),
        region=inputs.get("region", "cn"),
        pile_type=inputs.get("pile_type", "public"),
        risk_level=inputs.get("risk_level", "low"),
        confidence=inputs.get("confidence", 1.0),
        payload=inputs.get("payload", {}),
        raw=raw,
        source=inputs.get("source", "dify"),
        ts=inputs.get("ts"),
    )


# ── JSON 序列化辅助 ──────────────────────────────────────────
def to_end_node_output(response: ChargeSceneResponse) -> str:
    """5081 节点的最终输出:JSON 字符串(供 5099 end)。"""
    return response.model_dump_json()


def from_dify_raw_output(raw_output: str | dict[str, Any]) -> dict[str, Any]:
    """从 Dify workflow 原始 output 解析 ChargeSceneResponse。

    Dify 5099 end 节点 output 应当是 JSON 字符串,
    我们尝试解析,失败时返回 _raw_output 字段(供上层决策)。
    """
    if isinstance(raw_output, dict):
        return raw_output
    try:
        return json.loads(raw_output)
    except (ValueError, TypeError):
        return {"_raw_output": raw_output, "_parse_error": "invalid JSON"}


# ── 验证函数: 5081 节点输出是否合规 ─────────────────────────
def validate_end_output(output: dict[str, Any]) -> tuple[bool, list[str]]:
    """验证 5081 输出是否满足 SPEC-A1 契约。

    Returns:
        (is_valid, errors) — errors 是错误描述列表
    """
    errors: list[str] = []

    if "scene" not in output:
        errors.append("missing required field: scene")
    elif output["scene"] not in CHARGE_SCENE_ENUMS:
        errors.append(f"invalid scene: {output['scene']}")

    for field in ("endpoint", "region", "pile_type", "risk_level"):
        if field not in output:
            errors.append(f"missing field: {field}")

    if "payload" not in output:
        errors.append("missing required field: payload")
    elif not isinstance(output["payload"], dict):
        errors.append("payload must be a dict")

    if "ts" not in output:
        errors.append("missing required field: ts")

    if "confidence" in output:
        c = output["confidence"]
        if not isinstance(c, (int, float)) or c < 0 or c > 1:
            errors.append(f"confidence out of range: {c}")

    return (len(errors) == 0, errors)
