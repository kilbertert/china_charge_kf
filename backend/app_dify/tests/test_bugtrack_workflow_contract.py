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
        conversation_id="conv-b-1",
        flow_state="IDLE",
        query_text="设备白名单显示暂无数据",
    )
    body = json.loads(result["body_json"])

    assert body == {
        "keyword": "设备白名单",
        "module": "设备白名单",
        "op_desc": "后台查看汽车桩时白名单显示暂无数据",
        "limit": 5,
        "conversation_id": "conv-b-1",
        "flow_state": "IDLE",
        "source_text": "设备白名单显示暂无数据",
        "force_new": True,
        "idempotency_key": body["idempotency_key"],
    }
    assert body["idempotency_key"].startswith("dify-search-")


def test_followup_search_reuses_current_draft_binding() -> None:
    node = _nodes()["6240build"]
    namespace: dict = {}
    exec(node["code"], namespace)
    result = namespace["main"](
        mokuai="设备白名单",
        search_keyword="白名单",
        op_desc="补充：仅汽车桩异常",
        conversation_id="conv-b-1",
        flow_state="await_confirm_new",
        query_text="补充一下，仅汽车桩异常",
    )
    assert json.loads(result["body_json"])["force_new"] is False


def test_add_and_update_requests_carry_relational_context() -> None:
    nodes = _nodes()
    add_ns: dict = {}
    exec(nodes["6260a"]["code"], add_ns)
    add_body = json.loads(
        add_ns["main"](
            mokuai="计费模板",
            caozuomiaoshu="保存后未生效",
            huanjing="后台",
            leixing="bug",
            conversation_id="conv-b-2",
            flow_state="await_confirm_new",
            query_text="确认记录",
        )["body_json"]
    )
    assert add_body["conversation_id"] == "conv-b-2"
    assert add_body["source_text"] == "确认记录"
    assert add_body["idempotency_key"].startswith("dify-add-")

    update_ns: dict = {}
    exec(nodes["6176a"]["code"], update_ns)
    update_body = json.loads(
        update_ns["main"](
            record_id="rec-1",
            feedback_zh="补充截图与复现条件",
            mokuai="计费模板",
            huanjing="后台",
            leixing="bug",
            conversation_id="conv-b-2",
            flow_state="await_confirm_modify",
            query_text="确认修改",
        )["body_json"]
    )
    assert update_body["conversation_id"] == "conv-b-2"
    assert update_body["idempotency_key"].startswith("dify-update-")


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
