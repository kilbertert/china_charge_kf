#!/usr/bin/env python3
"""Apply the reply-quality fixes to the checked-in A/B chatflow DSLs.

The script is intentionally idempotent. It only changes the two source DSLs;
production Dify versions are patched separately after the local contract tests
pass.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent
A_PATH = ROOT / "charge_charging_A.yml"
B_PATH = ROOT / "charge_charging_B.yml"


def node_map(graph: dict) -> dict[str, dict]:
    return {str(node["id"]): node for node in graph["nodes"]}


def edge_map(graph: dict) -> dict[str, dict]:
    return {str(edge["id"]): edge for edge in graph["edges"]}


def edge_node_type(node: dict) -> str:
    """Return the legacy node type Dify expects in edge metadata."""
    node_type = node.get("data", {}).get("type", "")
    return "variable-assigner" if node_type == "assigner" else node_type


def add_assigner_item(node: dict, variable: str, source: list) -> None:
    """Write a Dify variable-assigner source selector correctly."""
    items = node.setdefault("data", {}).setdefault("items", [])
    for item in items:
        if item.get("variable_selector") == ["conversation", variable]:
            item["value"] = source
            item["input_type"] = "variable"
            item["operation"] = "over-write"
            item["variable_selector"] = ["conversation", variable]
            return
    items.append(
        {
            "input_type": "variable",
            "operation": "over-write",
            "value": source,
            "variable_selector": ["conversation", variable],
        }
    )


def add_edge(
    graph: dict, edge_id: str, source: str, source_handle: str, target: str
) -> None:
    edges = edge_map(graph)
    edge = edges.get(edge_id)
    nodes = node_map(graph)
    source_type = edge_node_type(nodes.get(source, {}))
    target_type = edge_node_type(nodes.get(target, {}))
    metadata = {"sourceType": source_type, "targetType": target_type}
    if edge is None:
        graph["edges"].append(
            {
                "data": metadata,
                "id": edge_id,
                "source": source,
                "sourceHandle": source_handle,
                "target": target,
                "targetHandle": "target",
                "type": "custom",
            }
        )
        return
    edge["source"] = source
    edge["sourceHandle"] = source_handle
    edge["target"] = target
    edge["targetHandle"] = "target"
    edge["data"] = metadata


def remove_edge(graph: dict, edge_id: str) -> None:
    graph["edges"] = [edge for edge in graph["edges"] if str(edge.get("id")) != edge_id]


def remove_node(graph: dict, node_id: str) -> None:
    """Remove a node and all edges touching it."""
    graph["nodes"] = [node for node in graph["nodes"] if str(node.get("id")) != node_id]
    graph["edges"] = [
        edge
        for edge in graph["edges"]
        if str(edge.get("source")) != node_id and str(edge.get("target")) != node_id
    ]


def clone_node(
    graph: dict,
    source_id: str,
    target_id: str,
    title: str,
    position: tuple[int, int],
) -> dict:
    """Clone an existing Dify node while keeping the patch idempotent."""
    source = copy.deepcopy(node_map(graph)[source_id])
    x, y = position
    source["id"] = target_id
    source["position"] = {"x": x, "y": y}
    source["positionAbsolute"] = {"x": x, "y": y}
    source.setdefault("data", {})["title"] = title
    target = node_map(graph).get(target_id)
    if target is None:
        graph["nodes"].append(source)
        return source
    target.clear()
    target.update(source)
    return target


def add_code_node(
    graph: dict,
    node_id: str,
    title: str,
    code: str,
    outputs: dict,
    variables: list[dict],
    position: tuple[int, int],
) -> None:
    nodes = node_map(graph)
    node = nodes.get(node_id)
    if node is None:
        x, y = position
        node = {
            "id": node_id,
            "type": "custom",
            "position": {"x": x, "y": y},
            "positionAbsolute": {"x": x, "y": y},
            "width": 242,
            "height": 88,
            "selected": False,
            "data": {
                "type": "code",
                "title": title,
                "code_language": "python3",
                "code": code,
                "variables": variables,
                "outputs": outputs,
            },
        }
        graph["nodes"].append(node)
    else:
        data = node.setdefault("data", {})
        data.update(
            {
                "type": "code",
                "title": title,
                "code_language": "python3",
                "code": code,
                "variables": variables,
                "outputs": outputs,
            }
        )


def patch_constants(graph: dict) -> None:
    node = node_map(graph)["6901"]
    data = node["data"]
    code = data.get("code", "")
    if (
        '"str_searching_initial"' not in code
        or '"str_searching_refined"' not in code
        or '"str_searching_denial"' not in code
    ):
        code = code.replace(
            '"str_idle": "IDLE",',
            '"str_idle": "IDLE",\n        "str_searching_initial": "searching_initial",\n        "str_searching_refined": "searching_refined",\n        "str_searching_denial": "searching_denial",',
        )
        data["code"] = code
    outputs = data.setdefault("outputs", {})
    outputs.setdefault("str_searching_initial", {"children": None, "type": "string"})
    outputs.setdefault("str_searching_refined", {"children": None, "type": "string"})
    outputs.setdefault("str_searching_denial", {"children": None, "type": "string"})


def patch_charge_b(graph: dict) -> None:
    nodes = node_map(graph)
    patch_constants(graph)

    # Initial B entry uses a separate raw-text pre-search chain. Reusing
    # 6240build here creates a directed cycle because the no-hit route later
    # reaches 6243-pre -> 6240build for the refined search.
    remove_edge(graph, "e-6601-default-6250")
    remove_edge(graph, "e-6601-default-6240build")
    remove_node(graph, "6240-search-state")
    remove_edge(graph, "e-6601-default-6240state")
    remove_edge(graph, "e-6240state-6240build")
    remove_node(graph, "6241-route")
    for old_node_id in (
        "6240-prebuild",
        "6240-pre",
        "6240-pre-parse",
        "6241-pre",
        "6242-pre",
        "6242b-pre",
        "6242c-pre",
    ):
        remove_node(graph, old_node_id)
    for edge_id in (
        "e-6241-default-6241route",
        "e-6241route-6250",
        "e-6241route-6250if",
        "e-6241route-denial-6243",
    ):
        remove_edge(graph, edge_id)
    nodes = node_map(graph)

    prebuild_code = """def main(query_text: str, conversation_id: str) -> dict:
    import hashlib, json, re
    query = (query_text or "").strip()
    keyword = query
    progress_patterns = (
        r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:解决|处理|修复)(?:了)?吗[？?]*$",
        r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:处理)?(?:到哪了|到什么进度|进度如何|进展如何|当前进度|处理进度)[？?]*$",
        r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:有结果|有进展)(?:了)?吗[？?]*$",
    )
    for pattern in progress_patterns:
        cleaned = re.sub(pattern, "", keyword).strip(" ，,。.!！?？")
        if cleaned:
            keyword = cleaned
            break
    anchors = (
        "白名单", "结算", "退款", "扫码", "支付", "计费", "费率", "优惠券",
        "发票", "预约", "导出", "导入", "登录", "注册", "充电", "订单", "设备",
    )
    keyword = next((term for term in anchors if term in keyword), keyword)
    if len(keyword) > 8:
        core = re.sub(r"(?:失败|异常|报错|无法|不能|不成功|不生效)$", "", keyword)
        keyword = (core[-4:] if core else keyword[:4]).strip() or keyword[:4]
    conv = (conversation_id or "").strip()
    idem_raw = "|".join([conv, "searching_initial", query, keyword])
    payload = {"keyword": keyword, "module": "", "op_desc": "", "limit": 5,
               "conversation_id": conv, "flow_state": "searching_initial",
               "source_text": query, "force_new": True,
               "idempotency_key": "dify-presearch-" + hashlib.sha256(idem_raw.encode("utf-8")).hexdigest()}
    return {"body_json": json.dumps(payload, ensure_ascii=False)}"""
    add_code_node(
        graph,
        "62405",
        "D2首轮原文预查body",
        prebuild_code,
        {"body_json": {"children": None, "type": "string"}},
        [
            {"variable": "query_text", "value_selector": ["6002", "query_text"]},
            {
                "variable": "conversation_id",
                "value_selector": ["sys", "conversation_id"],
            },
        ],
        (1590, 520),
    )

    pre_http = clone_node(
        graph, "6240", "62406", "D2首轮原文预查", (1840, 520)
    )
    pre_http["data"]["body"]["data"] = [
        {"type": "text", "value": "{{#62405.body_json#}}"}
    ]

    preparse_code = """def main(http_body: str, query_text: str) -> dict:
    import json, re
    from difflib import SequenceMatcher

    def norm(value: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").lower())

    def strip_progress(value: str) -> str:
        cleaned = norm(value)
        patterns = (
            r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:解决|处理|修复)(?:了)?吗$",
            r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:处理)?(?:到哪了|到什么进度|进度如何|进展如何|当前进度|处理进度)$",
            r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:有结果|有进展)(?:了)?吗$",
        )
        for pattern in patterns:
            updated = re.sub(pattern, "", cleaned)
            if updated != cleaned:
                return updated
        return cleaned

    def local_score(hit: dict, query: str) -> float:
        module = norm(hit.get("module") or "")
        record = norm(hit.get("op_desc") or hit.get("summary") or "")
        q = strip_progress(query)
        combined = module + record
        if not q or not record:
            return 0.0
        if q == record:
            return 160.0
        if len(q) >= 4 and (q in record or record in q):
            return 140.0
        bigrams = {q[index:index + 2] for index in range(len(q) - 1)}
        overlap = sum(1 for term in bigrams if term in combined)
        coverage = overlap / max(1, len(bigrams))
        anchors = ("白名单", "结算", "退款", "扫码", "支付", "计费", "费率",
                   "优惠券", "发票", "预约", "导出", "导入", "登录", "注册",
                   "充电", "订单", "设备")
        anchor_bonus = 20.0 if any(term in q and term in combined for term in anchors) else 0.0
        return coverage * 200.0 + anchor_bonus + SequenceMatcher(None, q, record).ratio() * 10.0

    try:
        data = json.loads(http_body or "{}")
    except Exception:
        return {"hit_record_id": "", "row_summary": ""}
    for hit in data.get("hits") or []:
        local = local_score(hit, query_text)
        try:
            raw_score = hit.get("match_score")
            score = max(float(raw_score), local) if raw_score is not None else local
            threshold = float(hit.get("match_threshold") or 125)
        except (TypeError, ValueError):
            score, threshold = local, 125
        if score < threshold:
            continue
        record_id = (hit.get("record_id") or "").strip()
        module = (hit.get("module") or "").strip()
        op_desc = (hit.get("op_desc") or hit.get("summary") or "").strip()
        parts = []
        for label, value in (("所属模块", module), ("问题描述", op_desc),
                             ("当前状态", hit.get("dev_status")),
                             ("产品回复", hit.get("reply")),
                             ("完成结果", hit.get("result"))):
            value = (value or "").strip()
            if value:
                parts.append(label + ":" + value)
        return {"hit_record_id": record_id,
                "row_summary": "\\n".join(parts) if parts else op_desc[:500]}
    return {"hit_record_id": "", "row_summary": ""}"""
    pre_parse = clone_node(
        graph, "6240-parse", "62407", "D2解析首轮预查", (2090, 520)
    )
    pre_parse["data"]["code"] = preparse_code
    pre_parse["data"]["variables"] = [
        {"variable": "http_body", "value_selector": ["62406", "body"]},
        {"variable": "query_text", "value_selector": ["6002", "query_text"]},
    ]

    pre_if = clone_node(
        graph, "6241", "62408", "D2首轮预查是否命中", (2340, 520)
    )
    pre_if["data"]["cases"] = [
        {
            "case_id": "bug_exist",
            "conditions": [
                {
                    "comparison_operator": "not empty",
                    "id": "cond_pre_hit",
                    "varType": "string",
                    "variable_selector": ["62407", "hit_record_id"],
                }
            ],
            "logical_operator": "and",
        },
        {
            "case_id": "default",
            "conditions": [
                {
                    "comparison_operator": "not empty",
                    "id": "cond_pre_default",
                    "varType": "string",
                    "variable_selector": ["6002", "query_text"],
                }
            ],
            "logical_operator": "and",
        },
    ]

    pre_reply = clone_node(
        graph, "6242", "62409", "D4首轮预查命中汇报", (2590, 420)
    )
    pre_reply["data"]["variables"] = [
        {
            "variable": "row_summary",
            "value_selector": ["62407", "row_summary"],
        },
        {"variable": "query_text", "value_selector": ["6002", "query_text"]},
    ]

    pre_bind = clone_node(
        graph, "6242b", "62410", "var_首轮预查命中绑定", (2840, 420)
    )
    for item in pre_bind["data"].get("items", []):
        if item.get("variable_selector") == ["conversation", "cv_record_id"]:
            item["value"] = ["62407", "hit_record_id"]
        elif item.get("variable_selector") == ["conversation", "cv_row_summary"]:
            item["value"] = ["62407", "row_summary"]

    pre_timer = clone_node(
        graph, "6242c", "62411", "首轮预查命中拼TIMER", (3090, 420)
    )
    pre_timer["data"]["variables"] = [
        {
            "variable": "llm_text",
            "value_selector": ["62409", "answer_text"],
        }
    ]

    add_edge(
        graph,
        "e-6601-default-62405",
        "6601",
        "default",
        "62405",
    )
    add_edge(
        graph,
        "e-62405-62406",
        "62405",
        "source",
        "62406",
    )
    add_edge(
        graph,
        "e-62406-62407",
        "62406",
        "source",
        "62407",
    )
    add_edge(
        graph,
        "e-62406-fail-6250",
        "62406",
        "fail-branch",
        "6250",
    )
    add_edge(
        graph,
        "e-62407-62408",
        "62407",
        "source",
        "62408",
    )
    add_edge(
        graph,
        "e-62408-hit-62409",
        "62408",
        "bug_exist",
        "62409",
    )
    add_edge(
        graph,
        "e-62408-default-6250",
        "62408",
        "default",
        "6250",
    )
    add_edge(
        graph,
        "e-62409-62410",
        "62409",
        "source",
        "62410",
    )
    add_edge(
        graph,
        "e-62410-62411",
        "62410",
        "source",
        "62411",
    )
    add_edge(
        graph,
        "e-62411-6098",
        "62411",
        "source",
        "6098",
    )
    add_edge(graph, "e-6240-fail-6250if", "6240", "fail-branch", "6250-if")
    nodes = node_map(graph)

    search_code = """def main(mokuai: str, search_keyword: str, op_desc: str, conversation_id: str, flow_state: str, query_text: str) -> dict:
    import hashlib, json
    state = (flow_state or "IDLE").strip()
    query = (query_text or "").strip()
    module = (mokuai or "").strip()
    keyword = (search_keyword or "").strip()
    desc = (op_desc or "").strip()
    force_new = state in ("IDLE", "searching_denial")
    idem_raw = "|".join([conv := (conversation_id or "").strip(), state, query, keyword, module])
    payload = {"keyword": keyword or module, "module": module, "op_desc": desc, "limit": 5,
               "conversation_id": conv, "flow_state": state, "source_text": query,
               "force_new": force_new,
               "idempotency_key": "dify-search-" + hashlib.sha256(idem_raw.encode("utf-8")).hexdigest()}
    return {"body_json": json.dumps(payload, ensure_ascii=False)}"""
    nodes["6240build"]["data"]["code"] = search_code

    # Refined no-hit keeps the existing sufficiency branch. Denial no-hit is
    # a dedicated case on the existing 6241 node, avoiding a second router.
    remove_node(graph, "6177-denial-confirm-state")
    remove_edge(graph, "e-6241route-denial-6177confirm")
    remove_edge(graph, "e-6177confirm-6244")
    cases = nodes["6241"]["data"].setdefault("cases", [])
    cases[:] = [case for case in cases if case.get("case_id") != "denial_search"]
    denial_case = {
        "case_id": "denial_search",
        "logical_operator": "and",
        "conditions": [
            {
                "comparison_operator": "is",
                "id": "cond_denial_search",
                "value": "searching_denial",
                "varType": "string",
                "variable_selector": ["conversation", "cv_flow_state"],
            }
        ],
    }
    default_index = next(
        (index for index, case in enumerate(cases) if case.get("case_id") == "default"),
        len(cases),
    )
    cases.insert(default_index, denial_case)
    add_edge(graph, "e-6241-denial-6243", "6241", "denial_search", "6243")

    # The refined search reuses the draft instead of creating a second one.
    for node_id in ("6243-pre", "6243b"):
        add_assigner_item(
            nodes[node_id],
            "cv_flow_state",
            ["6901", "str_searching_refined"],
        )
    add_assigner_item(
        nodes["6243"],
        "cv_flow_state",
        ["6901", "str_await_confirm_new"],
    )

    # Denial now preserves the new clue and re-runs the same search path.
    deny = nodes["6177-assigner"]
    add_assigner_item(deny, "cv_flow_state", ["6901", "str_searching_denial"])
    for field, source in (
        ("cv_feedback_zh", ["6177-parse", "caozuomiaoshu"]),
        ("cv_mokuai", ["6177-parse", "mokuai"]),
        ("cv_huanjing", ["6177-parse", "huanjing"]),
        ("cv_leixing", ["6177-parse", "leixing"]),
    ):
        add_assigner_item(deny, field, source)
    remove_node(graph, "6177-deny-out")
    nodes = node_map(graph)
    nodes["6098"]["data"]["variables"] = [
        selector
        for selector in nodes["6098"]["data"].get("variables", [])
        if not (isinstance(selector, list) and selector[0] == "6177-deny-out")
    ]
    nodes["6098"]["data"]["variables"] = [
        selector
        for selector in nodes["6098"]["data"]["variables"]
        if not (
            isinstance(selector, list)
            and selector[0] in {"6242c-pre", "62411"}
        )
    ]
    nodes["6098"]["data"]["variables"].append(["62411", "answer_text"])
    # A genuinely new topic should also perform the raw pre-search. This keeps
    # the same dedup-before-questioning invariant after a multi-turn topic
    # switch.
    add_edge(graph, "e-6177a-denyout", "6177-assigner", "source", "6240build")
    add_edge(
        graph,
        "e-6171bbugreset-6250",
        "6171b-bug-reset",
        "source",
        "62405",
    )

    # Accept the API score when available. Production may temporarily run an
    # older Bug API, so compute the same score locally when fields are absent.
    nodes["6240-parse"]["data"][
        "code"
    ] = """def main(http_body: str, cv_mokuai: str, cv_search_keyword: str = "", cv_feedback_zh: str = "") -> dict:
    import json, re
    from difflib import SequenceMatcher

    def norm(value: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").lower())

    def strip_progress(value: str) -> str:
        cleaned = norm(value)
        patterns = (
            r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:解决|处理|修复)(?:了)?吗$",
            r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:处理)?(?:到哪了|到什么进度|进度如何|进展如何|当前进度|处理进度)$",
            r"(?:这个问题|该问题)?(?:现在|目前|当前)?(?:有结果|有进展)(?:了)?吗$",
        )
        for pattern in patterns:
            updated = re.sub(pattern, "", cleaned)
            if updated != cleaned:
                return updated
        return cleaned

    def local_score(hit: dict) -> float:
        record_module = norm(hit.get("module") or "")
        record_op = norm(hit.get("op_desc") or hit.get("summary") or "")
        query_module = norm(cv_mokuai)
        query_op = strip_progress(cv_feedback_zh)
        query_keyword = strip_progress(cv_search_keyword)
        if record_module and record_module in record_op:
            record_op = record_op.replace(record_module, "", 1)
        if query_module and query_module in query_op:
            query_op = query_op.replace(query_module, "", 1)
        score = 0.0
        if query_module and record_module:
            if query_module == record_module:
                score += 100.0
            elif query_module in record_module or record_module in query_module:
                score += 60.0
        if query_keyword and query_keyword in record_op:
            score += 45.0
        if query_op and record_op:
            score += SequenceMatcher(None, query_op, record_op).ratio() * 40.0
        return score

    try:
        data = json.loads(http_body or "{}")
    except Exception:
        return {"hit_record_id": "", "row_summary": ""}
    hits = data.get("hits") or []
    if not hits:
        return {"hit_record_id": "", "row_summary": ""}
    for h in hits:
        try:
            raw_score = h.get("match_score")
            local = local_score(h)
            score = max(float(raw_score), local) if raw_score is not None else local
            threshold = float(h.get("match_threshold") or 125)
        except (TypeError, ValueError):
            score, threshold = local_score(h), 125
        if score < threshold:
            continue
        rid = h.get("record_id", "")
        module = (h.get("module") or "").strip()
        op_desc = (h.get("op_desc") or h.get("summary") or "").strip()
        if module and op_desc.startswith(module):
            op_desc = op_desc[len(module):].lstrip()
        op_desc = re.sub(r"^(所属模块|模块|功能点)[:：][^,，\\n]{1,30}[,，\\s]*", "", op_desc).strip()
        cv_mok = (cv_mokuai or "").strip()
        if cv_mok and module and (cv_mok not in module) and (module not in cv_mok):
            continue
        parts = []
        for label, key in (("所属模块", "module"), ("问题描述", "op_desc"),
                           ("当前状态", "dev_status"), ("产品回复", "reply"),
                           ("完成结果", "result")):
            value = (h.get(key) or "").strip()
            if value:
                parts.append(label + ":" + (op_desc if key == "op_desc" else value))
        return {"hit_record_id": rid, "row_summary": "\\n".join(parts) if parts else op_desc[:500]}
    return {"hit_record_id": "", "row_summary": ""}"""
    parse_variables = nodes["6240-parse"]["data"].setdefault("variables", [])
    for variable, selector in (
        ("cv_search_keyword", ["conversation", "cv_search_keyword"]),
        ("cv_feedback_zh", ["conversation", "cv_feedback_zh"]),
    ):
        current = next(
            (item for item in parse_variables if item.get("variable") == variable),
            None,
        )
        if current is None:
            parse_variables.append({"variable": variable, "value_selector": selector})
        else:
            current["value_selector"] = selector

    # Existing-record progress questions should be answered in the first turn.
    nodes["6242"]["data"][
        "code"
    ] = """def main(row_summary: str, query_text: str) -> dict:
    s = (row_summary or "").strip() or "该记录当前暂无详细状态"
    q = (query_text or "").strip()
    progress_terms = ("解决了吗", "处理了吗", "有结果吗", "有结果了吗", "有进展了吗", "当前进度", "处理进度", "什么进度", "进度如何", "进展如何", "处理到哪了", "怎么样了", "修复了吗")
    if any(term in q for term in progress_terms):
        return {"answer_text": "您反馈的问题当前进度如下：\\n" + s}
    return {"answer_text": "您好,这个问题我们之前已经记录在跟进中了:\\n" + s + "\\n\\n请问您这次反馈的是同一个问题吗?"}"""
    if not any(
        v.get("variable") == "query_text"
        for v in nodes["6242"]["data"].get("variables", [])
    ):
        nodes["6242"]["data"].setdefault("variables", []).append(
            {"variable": "query_text", "value_selector": ["6002", "query_text"]}
        )

    confirm_prompt = nodes["6244"]["data"].get("prompt_template", [])[0].get(
        "text", ""
    )
    if "不得承诺处理时效" not in confirm_prompt:
        confirm_prompt += (
            "\n6. 不得承诺处理时效或修复结果，禁止使用“尽快排查/尽快修复/"
            "尽快解决/预计完成”等表述；只说明确认后会记录并跟进。"
        )
        nodes["6244"]["data"]["prompt_template"][0]["text"] = confirm_prompt

    sanitizer_code = """def main(answer_text: str) -> dict:
    import re
    text = answer_text or ""
    replacement = "在您确认后，我们会为您记录并持续跟进"
    text = re.sub(
        r"(?:我们)?(?:将|会)?尽快(?:进行)?(?:排查(?:并)?)?(?:修复|解决|处理)",
        replacement,
        text,
    )
    text = re.sub(
        r"(?:我们)?(?:将|会)?及时(?:修复|解决)",
        replacement,
        text,
    )
    text = re.sub(
        r"预计[^。！？\\n]{0,30}(?:完成|上线|修复)",
        "具体进展以实际跟进结果为准",
        text,
    )
    return {"answer_text": text}"""
    add_code_node(
        graph,
        "60985",
        "最终答复承诺清洗",
        sanitizer_code,
        {"answer_text": {"children": None, "type": "string"}},
        [{"variable": "answer_text", "value_selector": ["6098", "output"]}],
        (3620, 520),
    )
    nodes = node_map(graph)
    remove_edge(graph, "e-6098-6099")
    add_edge(graph, "e-6098-60985", "6098", "source", "60985")
    add_edge(graph, "e-60985-6099", "60985", "source", "6099")
    nodes["6099"]["data"]["answer"] = "{{#60985.answer_text#}}"
    nodes["6099"]["data"]["variables"] = [
        {"value_selector": ["60985", "answer_text"], "variable": "final_text"}
    ]


def patch_charge_a(graph: dict) -> None:
    nodes = node_map(graph)

    # The visual model is only useful when a real attachment exists. Keep the
    # same image description contract for direct Dify consumers, but bypass the
    # model completely for ordinary text requests.
    add_code_node(
        graph,
        "6001-file-check",
        "检查是否包含图片",
        """def main(files: list) -> dict:
    return {"has_image": any(isinstance(item, dict) and item.get("type") == "image" for item in (files or []))}""",
        {"has_image": {"children": None, "type": "boolean"}},
        [{"variable": "files", "value_selector": ["sys", "files"]}],
        (-700, 0),
    )
    file_gate = clone_node(
        graph, "6003", "6001-file-gate", "是否包含图片", (-620, 0)
    )
    file_gate["data"]["cases"] = [
        {
            "case_id": "has_files",
            "conditions": [
                {
                    "comparison_operator": "is",
                    "id": "cond_has_files",
                    "value": True,
                    "varType": "boolean",
                    "variable_selector": ["6001-file-check", "has_image"],
                }
            ],
            "logical_operator": "and",
        },
        {
            "case_id": "default",
            "conditions": [
                {
                    "comparison_operator": "is",
                    "id": "cond_no_files",
                    "value": False,
                    "varType": "boolean",
                    "variable_selector": ["6001-file-check", "has_image"],
                }
            ],
            "logical_operator": "and",
        },
    ]
    vision = clone_node(graph, "6111", "6100", "图片内容识别", (-360, -120))
    vision["data"].update(
        {
            "type": "llm",
            "title": "图片内容识别",
            "model": {
                "mode": "chat",
                "name": "Doubao-Seed-2.0-lite",
                "provider": "langgenius/volcengine_maas/volcengine_maas",
            },
            "context": {"enabled": False, "variable_selector": []},
            "prompt_template": [
                {
                    "id": "v-sys",
                    "role": "system",
                    "text": "识别图片中的可见文字，并使用与图片文字相同的语言输出一句话。只保留设备编号、故障、界面内容和报错等关键信息。",
                },
                {
                    "id": "v-user",
                    "role": "user",
                    "text": "Please identify the image content.",
                },
            ],
            "vision": {
                "enabled": True,
                "configs": {"detail": "high", "variable_selector": ["sys", "files"]},
            },
        }
    )
    add_code_node(
        graph,
        "6100-no-image",
        "无图直接通过",
        'def main() -> dict:\n    return {"text": "无图"}',
        {"text": {"children": None, "type": "string"}},
        [],
        (-360, 100),
    )
    image_merge = clone_node(
        graph, "6098", "6100-merge", "汇聚图片描述", (-100, 0)
    )
    image_merge["data"]["title"] = "汇聚图片描述"
    image_merge["data"]["variables"] = [
        ["6100", "text"],
        ["6100-no-image", "text"],
    ]
    image_merge["data"]["output_type"] = "string"
    image_merge["data"]["outputs"] = {
        "output": {"children": None, "type": "string"}
    }
    nodes = node_map(graph)
    nodes["6002"]["data"]["code"] = """def main(query: str, input_language: str, image_desc: str) -> dict:
    text = (query or "").strip()
    desc = (image_desc or "").strip()
    query_text = f"{text} [image content: {desc}]" if text and desc and desc != "无图" else (f"[image content: {desc}]" if desc and desc != "无图" else text)
    if input_language and input_language.strip():
        lang = input_language.strip()
    else:
        cjk = sum(1 for c in query_text if '\u4e00' <= c <= '\u9fff')
        thai = any(0x0E00 <= ord(c) <= 0x0E7F for c in query_text)
        devanagari = any(0x0900 <= ord(c) <= 0x097F for c in query_text)
        vi_chars = "ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỵỷỹ"
        if thai:
            lang = "th"
        elif devanagari:
            lang = "ne"
        elif any(c in vi_chars for c in query_text):
            lang = "vi"
        elif cjk > 0:
            lang = "zh"
        else:
            lang = "en"
    return {"query_text": query_text, "language": lang}"""
    nodes["6002"]["data"]["variables"] = [
        {"value_selector": ["sys", "query"], "variable": "query"},
        {"value_selector": ["6001", "input_language"], "variable": "input_language"},
        {"value_selector": ["6100-merge", "output"], "variable": "image_desc"},
    ]
    for edge_id in ("e-6001-6002", "e-6001-6100", "e-6100-6002"):
        remove_edge(graph, edge_id)
    remove_edge(graph, "e-6001-file-gate")
    add_edge(graph, "e-6001-file-check", "6001", "source", "6001-file-check")
    add_edge(
        graph,
        "e-file-check-gate",
        "6001-file-check",
        "source",
        "6001-file-gate",
    )
    add_edge(graph, "e-file-gate-has-6100", "6001-file-gate", "has_files", "6100")
    add_edge(
        graph,
        "e-file-gate-default-no-image",
        "6001-file-gate",
        "default",
        "6100-no-image",
    )
    add_edge(graph, "e-6100-merge", "6100", "source", "6100-merge")
    add_edge(
        graph,
        "e-no-image-merge",
        "6100-no-image",
        "source",
        "6100-merge",
    )
    add_edge(graph, "e-image-merge-6002", "6100-merge", "source", "6002")

    early_bug_code = """def main(query_text: str) -> dict:
    query = (query_text or "").strip().lower()
    progress = ("解决了吗", "修复了吗", "处理了吗", "有结果了吗", "有进展了吗", "当前进度", "处理进度", "进度如何", "进展如何", "处理到哪了", "处理到什么进度")
    failures = ("报错", "失败", "异常", "用不了", "不生效", "没反应", "丢失", "崩溃", "闪退", "空白", "充不上", "中断")
    capability = any(term in query for term in ("能不能", "可不可以", "是否可以"))
    inability = not capability and any(term in query for term in ("无法", "不能"))
    return {"is_bug": any(term in query for term in progress + failures) or inability}"""
    add_code_node(
        graph,
        "6002-bug-route",
        "显式故障/进度早路由",
        early_bug_code,
        {"is_bug": {"children": None, "type": "boolean"}},
        [{"variable": "query_text", "value_selector": ["6002", "query_text"]}],
        (-220, 0),
    )
    early_if = clone_node(
        graph, "6003", "6002-bug-if", "显式故障直接转B", (20, 0)
    )
    early_if["data"]["cases"] = [
        {
            "case_id": "bug",
            "conditions": [
                {
                    "comparison_operator": "is",
                    "id": "cond_explicit_bug",
                    "value": True,
                    "varType": "boolean",
                    "variable_selector": ["6002-bug-route", "is_bug"],
                }
            ],
            "logical_operator": "and",
        },
        {
            "case_id": "default",
            "conditions": [
                {
                    "comparison_operator": "is",
                    "id": "cond_normal_query",
                    "value": False,
                    "varType": "boolean",
                    "variable_selector": ["6002-bug-route", "is_bug"],
                }
            ],
            "logical_operator": "and",
        },
    ]
    remove_edge(graph, "e-6002-6003")
    add_edge(graph, "e-6002-bug-route", "6002", "source", "6002-bug-route")
    add_edge(graph, "e-bug-route-if", "6002-bug-route", "source", "6002-bug-if")
    add_edge(
        graph,
        "e-bug-if-bug-switch",
        "6002-bug-if",
        "bug",
        "6201-switch-bug",
    )
    add_edge(graph, "e-bug-if-default-6003", "6002-bug-if", "default", "6003")

    # FAQ remains a fast answer, but explicit faults/progress queries must reach B.
    faq_gate_code = """def main(faq_text: str, query_text: str) -> dict:
    answer = faq_text or ""
    query = (query_text or "").strip()
    terms = ("报错", "无法", "不能", "用不了", "失败", "异常", "没反应", "不生效", "充不上", "中断", "解决了吗", "处理了吗", "有结果吗")
    if any(term in query for term in terms):
        answer += "\\n<!--SYS:SWITCH_TO_BUG-->"
    return {"answer_text": answer}"""
    add_code_node(
        graph,
        "6111-faq-gate",
        "FAQ后故障/进度闸门",
        faq_gate_code,
        {"answer_text": {"children": None, "type": "string"}},
        [
            {"variable": "faq_text", "value_selector": ["6111", "text"]},
            {"variable": "query_text", "value_selector": ["6002", "query_text"]},
        ],
        (1400, 220),
    )
    nodes = node_map(graph)
    add_edge(graph, "e-6111-faq-gate", "6111", "source", "6111-faq-gate")
    add_edge(graph, "e-6111-gate-6098", "6111-faq-gate", "source", "6098")
    remove_edge(graph, "e-6111-6098")
    aggregator = nodes["6098"]["data"]
    aggregator["variables"] = [
        selector
        for selector in aggregator.get("variables", [])
        if selector != ["6111", "text"]
    ]
    if ["6111-faq-gate", "answer_text"] not in aggregator["variables"]:
        aggregator["variables"].append(["6111-faq-gate", "answer_text"])

    prompt = nodes["6201"]["data"].get("instruction", "")
    prompt = prompt.replace(
        "等功能失效表述,或带截图反馈问题 → class_d",
        "等功能失效表述 → class_d",
    )
    if "【进度查询】" not in prompt:
        prompt = prompt.replace(
            "2. 【功能位置】",
            "1.5 【进度查询】用户询问已有问题是否解决/当前处理状态(如“解决了吗”“处理到哪了”) → class_d\n2. 【功能位置】",
        )
        if "【进度查询】" not in prompt:
            prompt += "\n\n【进度查询】已有故障、工单或历史反馈的解决状态/处理进度问题统一归 class_d。"
    nodes["6201"]["data"]["instruction"] = prompt

    # Production has separate business-rule and complete SOP datasets. Keep
    # these production IDs explicit so a local-environment UUID cannot break
    # retrieval when the graph is patched in place.
    nodes["6220"]["data"]["dataset_ids"] = ["39659847-228a-402c-a18a-3ce9334565a4"]
    nodes["6230"]["data"]["dataset_ids"] = ["b310c0a9-7b5a-4793-b8d0-0a111e3040d1"]
    nodes["6230"]["data"]["title"] = "C2 查询流程操作手册"

    # Retrieval snippets are evidence, not permission to infer prerequisites.
    # This guard is shared by every customer-facing A answer node.
    fact_boundary = """

【回答事实边界】
- 只能输出检索片段明确支持的菜单、步骤、限制或功能；不得凭常识补充“必须先审核/先登录/先筛选”等前置条件。
- 不得把“可能、通常、应当”改写成用户已经完成或尚未完成的事实，也不得承诺检索片段没有给出的结果、时效或产品能力。
- 多端或多版本路径冲突时必须标明适用端；端类型不明时只给已确认的路径并请求补充端类型，不得混合菜单。
- 检索片段不足以回答时，明确说明“该问题暂未收录”，不要用推测填空。
""".strip()
    for node_id in ("6111", "6212", "6221", "6231"):
        prompt_template = nodes[node_id]["data"].get("prompt_template") or []
        for item in prompt_template:
            if item.get("role") == "system":
                text = item.get("text", "")
                if "【回答事实边界】" not in text:
                    item["text"] = text.rstrip() + "\n\n" + fact_boundary
    faq_prompt = nodes["6111"]["data"].get("prompt_template") or []
    for item in faq_prompt:
        if item.get("role") == "system":
            item["text"] = item["text"].replace(
                "如果检索到相关结果(即使问题不完全匹配),要整合已有内容给用户排查指引",
                "只有检索片段直接支持用户问题时才整合回答；主题相近但不直接支持时按未收录处理",
            )
    menu_prompt = nodes["6212"]["data"].get("prompt_template") or []
    for item in menu_prompt:
        if item.get("role") == "system":
            item["text"] = re.sub(
                r"3\. 格式示例:.*?4\. 若检索结果为空",
                "3. 按检索片段原文输出路径，不自行举例或补充菜单。\n4. 若检索结果为空",
                item["text"],
                flags=re.S,
            )
    process_prompt = nodes["6231"]["data"].get("prompt_template") or []
    for item in process_prompt:
        if item.get("role") == "system":
            item["text"] = item["text"].replace(
                "基于上下文,指出当前流程及前置流程可能缺失/未完成的操作步骤",
                "只复述上下文明确记录的当前流程和步骤；上下文未明确记录的前置条件不得推测或写成用户待完成事项",
            )


def patch_file(path: Path, patcher) -> None:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    if path == A_PATH:
        yaml.indent(mapping=2, sequence=4, offset=2)
    else:
        # App B was exported with unindented sequences, explicit ``null`` and
        # very wide double-quoted code scalars. Preserve that style so applying
        # this patch does not create a repository-wide formatting diff.
        yaml.width = 100_000
        yaml.representer.add_representer(
            type(None),
            lambda representer, _value: representer.represent_scalar(
                "tag:yaml.org,2002:null", "null"
            ),
        )
    with path.open(encoding="utf-8") as handle:
        document = yaml.load(handle)
    patcher(document["workflow"]["graph"])
    if path == B_PATH:
        for variable in document["workflow"].get("conversation_variables", []):
            if variable.get("name") == "cv_flow_state":
                variable["description"] = (
                    "二阶段主状态机: IDLE/searching_initial/searching_refined/"
                    "searching_denial/await_confirm_identity/await_diff/"
                    "await_diff_decision/await_confirm_modify/await_confirm_new"
                )
                break
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(document, handle)


if __name__ == "__main__":
    patch_file(A_PATH, patch_charge_a)
    patch_file(B_PATH, patch_charge_b)
    print("patched charge reply-quality DSLs")
