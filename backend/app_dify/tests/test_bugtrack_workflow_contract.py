"""Bug 追踪工作流的图片理解与查重请求契约。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


YML_PATH = (
    Path(__file__).resolve().parents[3]
    / "Workflow-China_charge_seriver-draft-9380"
    / "workflow"
    / "charge_charging_B.yml"
)


def _nodes() -> dict[str, dict]:
    graph = yaml.safe_load(YML_PATH.read_text(encoding="utf-8"))["workflow"]["graph"]
    return {str(node["id"]): node["data"] for node in graph["nodes"]}


def test_structuring_nodes_consume_uploaded_images() -> None:
    nodes = _nodes()
    for node_id in ("6250", "6250b"):
        vision = nodes[node_id]["vision"]
        assert vision["enabled"] is True
        assert vision["configs"]["variable_selector"] == ["sys", "files"]


def test_search_request_keeps_keyword_module_and_operation_description() -> None:
    node = _nodes()["6240build"]
    namespace: dict = {}
    exec(node["code"], namespace)

    result = namespace["main"](
        mokuai="设备白名单",
        search_keyword="",
        op_desc="后台查看汽车桩时白名单显示暂无数据",
    )
    body = json.loads(result["body_json"])

    assert body == {
        "keyword": "设备白名单",
        "module": "设备白名单",
        "op_desc": "后台查看汽车桩时白名单显示暂无数据",
        "limit": 5,
    }

