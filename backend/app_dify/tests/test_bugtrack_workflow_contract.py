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
A_YML_PATH = YML_PATH.with_name("charge_charging_A.yml")


def _nodes() -> dict[str, dict]:
    graph = yaml.safe_load(YML_PATH.read_text(encoding="utf-8"))["workflow"]["graph"]
    return {str(node["id"]): node["data"] for node in graph["nodes"]}


def _graph(path: Path = YML_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["workflow"]["graph"]


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
        flow_state="searching_refined",
        query_text="设备白名单显示暂无数据",
    )
    body = json.loads(result["body_json"])

    assert body == {
        "keyword": "设备白名单",
        "module": "设备白名单",
        "op_desc": "后台查看汽车桩时白名单显示暂无数据",
        "limit": 5,
        "conversation_id": "conv-b-1",
        "flow_state": "searching_refined",
        "source_text": "设备白名单显示暂无数据",
        "force_new": False,
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


def test_initial_search_uses_raw_text_before_structuring() -> None:
    node = _nodes()["62405"]
    namespace: dict = {}
    exec(node["code"], namespace)
    body = json.loads(
        namespace["main"](
            conversation_id="conv-b-raw",
            query_text="订单结算失败",
        )["body_json"]
    )
    assert body["keyword"] == "结算"
    assert body["module"] == ""
    assert body["op_desc"] == ""
    assert body["force_new"] is True
    assert body["flow_state"] == "searching_initial"


def test_initial_progress_search_removes_status_suffix() -> None:
    node = _nodes()["62405"]
    namespace: dict = {}
    exec(node["code"], namespace)
    body = json.loads(
        namespace["main"](
            conversation_id="conv-b-progress",
            query_text="订单结算失败解决了吗",
        )["body_json"]
    )
    assert body["keyword"] == "结算"


def test_natural_progress_phrase_matches_ranked_existing_bug() -> None:
    nodes = _nodes()
    query = "设备白名单执行重置后原有数据丢失，这个问题现在处理到什么进度？"
    candidate = {
        "record_id": "rec-whitelist-reset",
        "module": "设备白名单",
        "op_desc": "Web后台充电桩模块，执行重置操作后，原配置白名单数据丢失，列表显示暂无数据。",
        "dev_status": "开发中",
    }

    prebuild_ns: dict = {}
    exec(nodes["62405"]["code"], prebuild_ns)
    body = json.loads(
        prebuild_ns["main"](query, "conv-progress-natural")["body_json"]
    )
    assert body["keyword"] == "白名单"

    parser_ns: dict = {}
    exec(nodes["62407"]["code"], parser_ns)
    result = parser_ns["main"](
        json.dumps({"hits": [candidate]}, ensure_ascii=False),
        query,
    )
    assert result["hit_record_id"] == "rec-whitelist-reset"
    assert "当前状态:开发中" in result["row_summary"]


def test_graph_searches_before_n5_information_request() -> None:
    graph = _graph()
    nodes = {str(node["id"]): node["data"] for node in graph["nodes"]}
    edges = {
        (str(edge["source"]), edge.get("sourceHandle"), str(edge["target"]))
        for edge in graph["edges"]
    }
    assert ("6601", "default", "62405") in edges
    assert ("62405", "source", "62406") in edges
    assert ("62406", "source", "62407") in edges
    assert ("62406", "fail-branch", "6250") in edges
    assert ("62407", "source", "62408") in edges
    assert ("62408", "default", "6250") in edges
    assert ("62408", "bug_exist", "62409") in edges
    assert ("6250-judge", "source", "6243-pre") in edges
    assert ("6243-pre", "source", "6240build") in edges
    assert ("6241", "default", "6250-if") in edges
    assert ("6601", "default", "6250") not in edges
    assert ("6601", "default", "6240build") not in edges
    assert "6240-search-state" not in nodes
    assert "6241-route" not in nodes
    assert "{{#62405.body_json#}}" in nodes["62406"]["body"]["data"][0]["value"]
    assert ("6240", "fail-branch", "6250-if") in edges
    state_item = next(
        item
        for item in nodes["6243"]["items"]
        if item["variable_selector"] == ["conversation", "cv_flow_state"]
    )
    assert state_item["value"] == ["6901", "str_await_confirm_new"]


def test_bugtrack_graph_is_acyclic() -> None:
    graph = _graph()
    node_ids = {str(node["id"]) for node in graph["nodes"]}
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in graph["edges"]:
        source, target = str(edge["source"]), str(edge["target"])
        if source in node_ids and target in node_ids:
            outgoing[source].append(target)
            incoming[target] += 1
    queue = [node_id for node_id, count in incoming.items() if count == 0]
    visited = 0
    while queue:
        source = queue.pop()
        visited += 1
        for target in outgoing[source]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    assert visited == len(node_ids), "Dify workflow graph contains a directed cycle"


def test_refined_search_reuses_presearch_draft() -> None:
    node = _nodes()["6240build"]
    namespace: dict = {}
    exec(node["code"], namespace)
    body = json.loads(
        namespace["main"](
            mokuai="订单管理",
            search_keyword="结算失败",
            op_desc="后台订单结算失败",
            conversation_id="conv-b-raw",
            flow_state="searching_refined",
            query_text="订单结算失败",
        )["body_json"]
    )
    assert body["module"] == "订单管理"
    assert body["op_desc"] == "后台订单结算失败"
    assert body["force_new"] is False


def test_d2_requires_similarity_threshold_before_existing_issue() -> None:
    node = _nodes()["6240-parse"]
    namespace: dict = {}
    exec(node["code"], namespace)
    hit = {
        "record_id": "rec-1",
        "module": "订单管理",
        "op_desc": "后台订单结算失败",
        "match_score": 130,
        "match_threshold": 125,
        "dev_status": "开发中",
    }
    assert (
        namespace["main"](json.dumps({"hits": [hit]}), "订单管理")["hit_record_id"]
        == "rec-1"
    )
    hit["match_score"] = 101
    assert (
        namespace["main"](json.dumps({"hits": [hit]}), "订单管理")["hit_record_id"]
        == ""
    )


def test_d2_scores_legacy_api_candidates_and_checks_beyond_first_hit() -> None:
    node = _nodes()["6240-parse"]
    namespace: dict = {}
    exec(node["code"], namespace)
    hits = [
        {
            "record_id": "rec-unrelated",
            "module": "订单管理",
            "op_desc": "订单详情页导出按钮点击后没有生成文件",
        },
        {
            "record_id": "rec-duplicate",
            "module": "订单管理",
            "op_desc": "后台订单结算时提示失败，订单无法完成结算",
        },
    ]
    result = namespace["main"](
        json.dumps({"hits": hits}),
        "订单管理",
        "结算失败",
        "后台订单结算操作失败，订单不能正常结算",
    )
    assert result["hit_record_id"] == "rec-duplicate"


def test_raw_presearch_accepts_identical_legacy_candidate() -> None:
    node = _nodes()["62407"]
    namespace: dict = {}
    exec(node["code"], namespace)
    result = namespace["main"](
        json.dumps(
            {
                "hits": [
                    {
                        "record_id": "rec-existing",
                        "module": "订单管理",
                        "op_desc": "后台查询订单后执行结算操作时失败，订单无法完成结算",
                        "dev_status": "开发中",
                    }
                ]
            }
        ),
        "订单结算失败解决了吗",
    )
    assert result["hit_record_id"] == "rec-existing"
    assert "当前状态:开发中" in result["row_summary"]


def test_raw_presearch_rejects_other_order_problem() -> None:
    node = _nodes()["62407"]
    namespace: dict = {}
    exec(node["code"], namespace)
    result = namespace["main"](
        json.dumps(
            {
                "hits": [
                    {
                        "record_id": "rec-refund",
                        "module": "订单退款",
                        "op_desc": "用户充电结束后剩余金额未自动退款",
                    }
                ]
            }
        ),
        "订单结算失败",
    )
    assert result["hit_record_id"] == ""


def test_progress_hit_is_answered_without_identity_question() -> None:
    node = _nodes()["6242"]
    namespace: dict = {}
    exec(node["code"], namespace)
    answer = namespace["main"]("当前状态:开发中", "这个问题解决了吗?")["answer_text"]
    assert "当前进度如下" in answer
    assert "是不是同一个问题" not in answer


def test_final_reply_sanitizer_removes_unfounded_commitment() -> None:
    graph = _graph()
    nodes = {str(node["id"]): node["data"] for node in graph["nodes"]}
    edges = {
        (str(edge["source"]), edge.get("sourceHandle"), str(edge["target"]))
        for edge in graph["edges"]
    }
    namespace: dict = {}
    exec(nodes["60985"]["code"], namespace)
    answer = namespace["main"]("我们将尽快排查修复，请您耐心等待。")[
        "answer_text"
    ]
    assert "尽快" not in answer
    assert "记录并持续跟进" in answer
    assert ("6098", "source", "60985") in edges
    assert ("60985", "source", "6099") in edges
    assert ("6098", "source", "6099") not in edges
    assert nodes["6099"]["answer"] == "{{#60985.answer_text#}}"
    assert "不得承诺处理时效" in nodes["6244"]["prompt_template"][0]["text"]


def test_denial_path_preserves_new_clue_and_rechecks() -> None:
    graph = _graph()
    nodes = {str(node["id"]): node["data"] for node in graph["nodes"]}
    edges = {
        (str(edge["source"]), edge.get("sourceHandle"), str(edge["target"]))
        for edge in graph["edges"]
    }
    deny_items = nodes["6177-assigner"]["items"]
    assert {
        tuple(item["value"])
        for item in deny_items
        if item["variable_selector"][-1] in {"cv_mokuai", "cv_feedback_zh"}
    } == {
        ("6177-parse", "mokuai"),
        ("6177-parse", "caozuomiaoshu"),
    }
    assert ("6177-assigner", "source", "6240build") in edges
    assert ("6241", "denial_search", "6243") in edges
    assert "6177-deny-out" not in nodes
    assert "6177-denial-confirm-state" not in nodes


def test_a_faq_gate_routes_faults_to_bug_app_and_uses_correct_kbs() -> None:
    graph = _graph(A_YML_PATH)
    nodes = {str(node["id"]): node["data"] for node in graph["nodes"]}
    edges = {
        (str(edge["source"]), edge.get("sourceHandle"), str(edge["target"]))
        for edge in graph["edges"]
    }
    assert ("6111", "source", "6111-faq-gate") in edges
    assert ("6111-faq-gate", "source", "6098") in edges
    assert ["6111", "text"] not in nodes["6098"]["variables"]
    assert ["6111-faq-gate", "answer_text"] in nodes["6098"]["variables"]
    gate_ns: dict = {}
    exec(nodes["6111-faq-gate"]["code"], gate_ns)
    assert (
        "SWITCH_TO_BUG" in gate_ns["main"]("FAQ answer", "订单结算失败")["answer_text"]
    )
    assert (
        "SWITCH_TO_BUG"
        not in gate_ns["main"]("FAQ answer", "怎么设置计费模板")["answer_text"]
    )
    assert "带截图反馈问题" not in nodes["6201"]["instruction"]
    assert "【进度查询】" in nodes["6201"]["instruction"]
    for node_id in ("6111", "6212", "6221", "6231"):
        system_prompts = [
            item["text"]
            for item in nodes[node_id]["prompt_template"]
            if item.get("role") == "system"
        ]
        assert any("【回答事实边界】" in text for text in system_prompts)
    assert "充电桩>计费模板管理" not in nodes["6212"]["prompt_template"][0]["text"]
    assert "可能缺失/未完成" not in nodes["6231"]["prompt_template"][0]["text"]
    assert nodes["6220"]["dataset_ids"] == ["39659847-228a-402c-a18a-3ce9334565a4"]
    assert nodes["6230"]["dataset_ids"] == ["b310c0a9-7b5a-4793-b8d0-0a111e3040d1"]


def test_a_skips_vision_without_files_and_routes_bugs_before_l1() -> None:
    graph = _graph(A_YML_PATH)
    nodes = {str(node["id"]): node["data"] for node in graph["nodes"]}
    edges = {
        (str(edge["source"]), edge.get("sourceHandle"), str(edge["target"]))
        for edge in graph["edges"]
    }

    assert ("6001", "source", "6001-file-check") in edges
    assert ("6001-file-check", "source", "6001-file-gate") in edges
    assert ("6001-file-gate", "has_files", "6100") in edges
    assert ("6001-file-gate", "default", "6100-no-image") in edges
    assert ("6100", "source", "6100-merge") in edges
    assert ("6100-no-image", "source", "6100-merge") in edges
    assert ("6100-merge", "source", "6002") in edges
    assert ("6001", "source", "6100") not in edges
    assert ("6002", "source", "6003") not in edges
    assert ("6002", "source", "6002-bug-route") in edges
    assert ("6002-bug-if", "bug", "6201-switch-bug") in edges
    assert ("6002-bug-if", "default", "6003") in edges

    no_image_ns: dict = {}
    exec(nodes["6100-no-image"]["code"], no_image_ns)
    assert no_image_ns["main"]() == {"text": "无图"}

    file_check_ns: dict = {}
    exec(nodes["6001-file-check"]["code"], file_check_ns)
    assert file_check_ns["main"]([]) == {"has_image": False}
    assert file_check_ns["main"]([{"type": "audio"}]) == {"has_image": False}
    assert file_check_ns["main"]([{"type": "image"}]) == {"has_image": True}

    route_ns: dict = {}
    exec(nodes["6002-bug-route"]["code"], route_ns)
    assert route_ns["main"]("订单结算失败")["is_bug"] is True
    assert route_ns["main"]("这个问题现在处理到什么进度")["is_bug"] is True
    assert route_ns["main"]("订单能不能导出")["is_bug"] is False


def test_charge_a_graph_is_acyclic() -> None:
    graph = _graph(A_YML_PATH)
    node_ids = {str(node["id"]) for node in graph["nodes"]}
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in graph["edges"]:
        source, target = str(edge["source"]), str(edge["target"])
        if source in node_ids and target in node_ids:
            outgoing[source].append(target)
            incoming[target] += 1
    queue = [node_id for node_id, count in incoming.items() if count == 0]
    visited = 0
    while queue:
        source = queue.pop()
        visited += 1
        for target in outgoing[source]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    assert visited == len(node_ids), "Dify A workflow graph contains a directed cycle"


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


def test_confirm_with_image_instruction_overrides_llm_modify_misclassification() -> (
    None
):
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
