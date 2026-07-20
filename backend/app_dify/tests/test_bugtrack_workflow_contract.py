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


def test_confirm_with_image_instruction_overrides_llm_modify_misclassification() -> None:
    node = _nodes()["6170-parse"]
    namespace: dict = {}
    exec(node["code"], namespace)

    assert namespace["main"](
        llm_text="MODIFY_NEW",
        query_text="是的记得把我图片上传",
    ) == {"label": "CONFIRM_NEW"}
    assert namespace["main"](
        llm_text="MODIFY_NEW",
        query_text="对的，截图也请一并附上",
    ) == {"label": "CONFIRM_NEW"}


def test_real_field_change_is_not_overridden_as_confirmation() -> None:
    node = _nodes()["6170-parse"]
    namespace: dict = {}
    exec(node["code"], namespace)

    assert namespace["main"](
        llm_text="MODIFY_NEW",
        query_text="是的，不过模板ID改成9876",
    ) == {"label": "MODIFY_NEW"}
    assert namespace["main"](
        llm_text="ABANDON",
        query_text="是的，但是算了不报了",
    ) == {"label": "ABANDON"}


def test_n5b_prompt_knows_h5_supports_images() -> None:
    prompt = next(
        item["text"]
        for item in _nodes()["6250b"]["prompt_template"]
        if item["id"] == "n5b-sys"
    )
    assert "当前 H5/客服窗口支持图片文件" in prompt
    assert "不得因本轮附件处理要求重新判为 INSUFFICIENT" in prompt
