#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 第二轮3核心修复: 否认循环/确认态新bug路由/ESCALATE旁路。

根因(第二轮E2E验证):
  P2-CRITICAL-1: 6177-assigner(DENY_IDENTITY)未清cv_search_keyword/cv_record_id/cv_row_summary
    +硬编码SUFFICIENT -> 6240build用旧keyword重查命中同一记录 -> D4死循环(否认后重复D4话术)。
  P2-CRITICAL-2: 6171b[default](IRRELEVANT)->6162->6162-switch-kb->KB_REENTRY,
    确认态发新bug描述被判IRRELEVANT切KB(空回复),不进bug流程。
  P1-HIGH: 6170无cv_clarify_count感知,IRRELEVANT->6171[default]->6162->KB_REENTRY,
    绕过6250b/ESCALATE(4轮模糊后应转人工实际切KB)。

业务:
  否认后应引导用户描述新问题(不重查旧记录,不存否认语为bug)
  确认态发新bug应进bug流程(细分BUG_NEW_TOPIC vs 真无关IRRELEVANT)
  已引导3次仍模糊应转人工(6170感知count,ESCALATE不被IRRELEVANT旁路)

修复(改draft+published):
  0. 6901 加 str_insufficient
  1. 6177-assigner items重写(清cv+INSUFFICIENT+clarify_count_1) + 删边->6240build
     + 新6177-deny-out(引导"请描述新问题"+cancel) ->6098
  2. 6170b prompt加BUG_NEW_TOPIC + 6171b加bug_new_topic case
     + 新6171b-bug-reset(清cv+IDLE) ->6250(bug入口)
  3. 6170 prompt注入cv_clarify_count+ESCALATE标签 + 6171加escalate case
     ->6250b-escalate-abort(转人工, 复用P1#3节点)

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_p2.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_p2.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 0. 6901 加 str_insufficient
NEW_6901_CODE = r'''def main() -> dict:
    return {
        "value_true": True,
        "value_false": False,
        "str_clarify": "clarify",
        "str_faq": "faq",
        "str_custom": "custom",
        "str_d": "d",
        "str_a": "a",
        "str_b": "b",
        "str_c": "c",
        "str_empty": "",
        "str_await_confirm_new": "await_confirm_new",
        "str_idle": "IDLE",
        "str_await_confirm_identity": "await_confirm_identity",
        "str_await_diff_decision": "await_diff_decision",
        "str_await_confirm_modify": "await_confirm_modify",
        "str_await_modify_window": "await_modify_window",
        "clarify_count_0": 0,
        "clarify_count_1": 1,
        "str_sufficient": "SUFFICIENT",
        "str_insufficient": "INSUFFICIENT"
    }'''

# 1. 6177-assigner 新 items (清cv+INSUFFICIENT+count=1, 不存否认语转写)
ITEMS_6177 = [
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_await_confirm_new"], "variable_selector": ["conversation", "cv_flow_state"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_insufficient"], "variable_selector": ["conversation", "cv_sufficiency_label"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "clarify_count_1"], "variable_selector": ["conversation", "cv_clarify_count"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_search_keyword"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_record_id"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_row_summary"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_feedback_zh"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_mokuai"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_huanjing"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_leixing"]},
]

DENY_OUT_CODE = r'''def main() -> dict:
    text = "好的,这不是您反馈的问题。请描述您遇到的新问题(如充电桩无法启动、订单未退款、设备故障等),我来帮您记录跟进~"
    return {"answer_text": text + "\n<!--SYS:TIMER|action=cancel-->"}'''

# 2. 6171b-bug-reset items (清cv+IDLE, 进bug流程前重置)
ITEMS_6171B_RESET = [
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_idle"], "variable_selector": ["conversation", "cv_flow_state"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_record_id"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_search_keyword"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_row_summary"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_feedback_zh"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_mokuai"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_huanjing"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_leixing"]},
    {"input_type": "variable", "operation": "over-write", "value": ["6901", "clarify_count_0"], "variable_selector": ["conversation", "cv_clarify_count"]},
]

# 6170b prompt 加 BUG_NEW_TOPIC
P6170B_OLD = "- IRRELEVANT       : 开新话题/无关"
P6170B_NEW = ("- BUG_NEW_TOPIC    : 用户开了新话题,且新话题是充电桩bug/故障反馈(另一个充电桩问题/设备故障/订单问题/充电异常)\n"
              "- IRRELEVANT       : 开新话题且与充电桩bug无关(查计费规则/怎么操作/咨询类)")

# 6170 prompt 注入 cv_clarify_count + ESCALATE
P6170_OLD_COUNT = "【用户新消息】: {{#6002.query_text#}}\n\n只输出一个分类标签"
P6170_NEW_COUNT = "【用户新消息】: {{#6002.query_text#}}\n【已引导补充次数】: {{#conversation.cv_clarify_count#}}\n\n只输出一个分类标签"
P6170_OLD_ESC = "- ABANDON          : 用户要结束/放弃本次反馈,不是开新话题(算了/不报了/没事/不用了/结束吧)\n- IRRELEVANT        : 开新话题/与待确认事项无关"
P6170_NEW_ESC = ("- ABANDON          : 用户要结束/放弃本次反馈,不是开新话题(算了/不报了/没事/不用了/结束吧)\n"
                 "- ESCALATE         : 已引导补充次数>=3 且用户仍模糊/说不清楚/无法提供有效信息(转人工)\n"
                 "- IRRELEVANT        : 开新话题/与待确认事项无关")

ESCALATE_CASE_6171 = {
    "case_id": "escalate", "logical_operator": "and",
    "conditions": [{"comparison_operator": "is", "id": "c_esc_6171", "value": "ESCALATE", "varType": "string", "variable_selector": ["6170", "text"]}],
}
BUG_NEW_TOPIC_CASE_6171B = {
    "case_id": "bug_new_topic", "logical_operator": "and",
    "conditions": [{"comparison_operator": "is", "id": "c_bnt_6171b", "value": "BUG_NEW_TOPIC", "varType": "string", "variable_selector": ["6170b", "text"]}],
}


def patch_graph(g):
    nodes = g["nodes"]; edges = g["edges"]
    touched = []
    # assigner 出边 sourceHandle (参考 6162-abort)
    abort_sh = "source"
    for e in edges:
        if e.get("source") == "6162-abort":
            abort_sh = e.get("sourceHandle", "source"); break
    # 6098 入边 targetHandle (参考 6162-out->6098)
    out_th = "target"
    for e in edges:
        if e.get("source") == "6162-out" and e.get("target") == "6098":
            out_th = e.get("targetHandle", "target"); break

    for n in nodes:
        nid = n.get("id"); d = n.get("data", {})
        # 0. 6901 加 str_insufficient
        if nid == "6901":
            d["code"] = NEW_6901_CODE
            outs = d.get("outputs", {})
            if "str_insufficient" not in outs:
                outs["str_insufficient"] = {"children": None, "type": "string"}
                d["outputs"] = outs
            touched.append("6901:+str_insufficient")
        # 1. 6177-assigner items 重写
        if nid == "6177-assigner":
            d["items"] = json.loads(json.dumps(ITEMS_6177))
            touched.append("6177-assigner:items重写(清cv+INSUFFICIENT)")
        # 2. 6170b prompt 加 BUG_NEW_TOPIC
        if nid == "6170b":
            txt = d.get("prompt_template", [{}])[0].get("text", "")
            if P6170B_OLD in txt and "BUG_NEW_TOPIC" not in txt:
                d["prompt_template"][0]["text"] = txt.replace(P6170B_OLD, P6170B_NEW, 1)
                touched.append("6170b:prompt+BUG_NEW_TOPIC")
        # 3. 6170 prompt 注入 count + ESCALATE
        if nid == "6170":
            txt = d.get("prompt_template", [{}])[0].get("text", "")
            if P6170_OLD_COUNT in txt and "cv_clarify_count" not in txt:
                txt = txt.replace(P6170_OLD_COUNT, P6170_NEW_COUNT, 1)
                touched.append("6170:prompt+cv_clarify_count")
            if P6170_OLD_ESC in txt and "ESCALATE" not in txt:
                txt = txt.replace(P6170_OLD_ESC, P6170_NEW_ESC, 1)
                touched.append("6170:prompt+ESCALATE标签")
            d["prompt_template"][0]["text"] = txt
        # 6171 加 escalate case
        if nid == "6171":
            cases = d.get("cases", [])
            if not any(c.get("case_id") == "escalate" for c in cases):
                # 在 abandon 后 default 前插
                ab_idx = next((i for i, c in enumerate(cases) if c.get("case_id") == "abandon"), None)
                if ab_idx is not None:
                    cases.insert(ab_idx + 1, json.loads(json.dumps(ESCALATE_CASE_6171)))
                    touched.append("6171:+escalate case")
        # 6171b 加 bug_new_topic case
        if nid == "6171b":
            cases = d.get("cases", [])
            if not any(c.get("case_id") == "bug_new_topic" for c in cases):
                ab_idx = next((i for i, c in enumerate(cases) if c.get("case_id") == "abandon"), None)
                if ab_idx is not None:
                    cases.insert(ab_idx + 1, json.loads(json.dumps(BUG_NEW_TOPIC_CASE_6171B)))
                    touched.append("6171b:+bug_new_topic case")

    # 1. 删边 6177-assigner -> 6240build
    eb = len(edges)
    edges[:] = [e for e in edges if not (e.get("source") == "6177-assigner" and e.get("target") == "6240build")]
    if len(edges) < eb:
        touched.append("删边 6177-assigner->6240build")
    # 1. 新节点 6177-deny-out
    if not any(n.get("id") == "6177-deny-out" for n in nodes):
        nodes.append({"id": "6177-deny-out", "type": "custom",
                      "position": {"x": 1260, "y": 220}, "positionAbsolute": {"x": 1260, "y": 220},
                      "width": 242, "height": 88, "selected": False,
                      "data": {"type": "code", "title": "否认引导话术", "code_language": "python3", "selected": False,
                               "code": DENY_OUT_CODE, "outputs": {"answer_text": {"children": None, "type": "string"}}, "variables": []}})
        touched.append("+6177-deny-out")
    # 6177-assigner -> 6177-deny-out (取 6177-assigner 出边 sourceHandle)
    a_sh = "source"
    for e in edges:
        if e.get("source") == "6177-assigner":
            a_sh = e.get("sourceHandle", "source"); break
    e1 = {"id": "e-6177a-denyout", "source": "6177-assigner", "sourceHandle": a_sh, "target": "6177-deny-out", "targetHandle": "target", "type": "custom"}
    e2 = {"id": "e-6177denyout-6098", "source": "6177-deny-out", "sourceHandle": "source", "target": "6098", "targetHandle": out_th, "type": "custom"}
    for e in [e1, e2]:
        if not any(ed.get("id") == e["id"] for ed in edges):
            edges.append(e); touched.append("edge %s" % e["id"])

    # 2. 新节点 6171b-bug-reset
    if not any(n.get("id") == "6171b-bug-reset" for n in nodes):
        nodes.append({"id": "6171b-bug-reset", "type": "custom",
                      "position": {"x": 740, "y": 340}, "positionAbsolute": {"x": 740, "y": 340},
                      "width": 242, "height": 88, "selected": False,
                      "data": {"type": "assigner", "version": "2", "title": "var_新bug重置cv", "selected": False,
                               "items": json.loads(json.dumps(ITEMS_6171B_RESET))}})
        touched.append("+6171b-bug-reset")
    # 6171b[bug_new_topic] -> 6171b-bug-reset -> 6250
    e3 = {"id": "e-6171b-bugreset", "source": "6171b", "sourceHandle": "bug_new_topic", "target": "6171b-bug-reset", "targetHandle": "target", "type": "custom"}
    e4 = {"id": "e-6171bbugreset-6250", "source": "6171b-bug-reset", "sourceHandle": abort_sh, "target": "6250", "targetHandle": "target", "type": "custom"}
    for e in [e3, e4]:
        if not any(ed.get("id") == e["id"] for ed in edges):
            edges.append(e); touched.append("edge %s" % e["id"])

    # 3. 6171[escalate] -> 6250b-escalate-abort
    e5 = {"id": "e-6171-esc-escalateabort", "source": "6171", "sourceHandle": "escalate", "target": "6250b-escalate-abort", "targetHandle": "target", "type": "custom"}
    if not any(ed.get("id") == e5["id"] for ed in edges):
        edges.append(e5); touched.append("edge 6171[escalate]->6250b-escalate-abort")

    return touched


def main():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, version, graph FROM workflows WHERE app_id=%s ORDER BY updated_at DESC", (BID,))
    rows = cur.fetchall()
    print("BID=%s  rows=%d (含draft)  APPLY=%s" % (BID, len(rows), APPLY))
    changed = 0
    for r in rows:
        g = r["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        touched = patch_graph(g)
        if not touched:
            continue
        if APPLY:
            cur.execute("UPDATE workflows SET graph=%s WHERE id=%s", (json.dumps(g, ensure_ascii=False), r["id"]))
            changed += cur.rowcount
        print("  %s ver=%s -> %s" % ("patched" if APPLY else "would-patch", str(r["version"])[:20], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s ORDER BY updated_at DESC LIMIT 1", (BID,))
        g = json.loads(cur.fetchone()["graph"])
        ids = [n.get("id") for n in g["nodes"]]
        print("  verify 6177-deny-out=%s | 6171b-bug-reset=%s" % ("6177-deny-out" in ids, "6171b-bug-reset" in ids))
        for n in g["nodes"]:
            if n.get("id") == "6901":
                print("  verify 6901 str_insufficient:", "str_insufficient" in (n["data"].get("outputs") or {}))
            if n.get("id") == "6177-assigner":
                items = n["data"].get("items", [])
                print("  verify 6177-assigner: INSUFFICIENT=", any(it.get("value") == ["6901", "str_insufficient"] for it in items), "| 清cv_search_keyword=", any(it.get("variable_selector") == ["conversation", "cv_search_keyword"] for it in items))
            if n.get("id") == "6170b":
                print("  verify 6170b BUG_NEW_TOPIC:", "BUG_NEW_TOPIC" in n["data"]["prompt_template"][0]["text"])
            if n.get("id") == "6170":
                print("  verify 6170 ESCALATE+count:", "ESCALATE" in n["data"]["prompt_template"][0]["text"], "cv_clarify_count" in n["data"]["prompt_template"][0]["text"])
            if n.get("id") in ("6171", "6171b"):
                cs = [c.get("case_id") for c in n["data"].get("cases", [])]
                print(f"  verify {n['id']} cases: {cs}")
        print("  verify edges:", [e["id"] for e in g["edges"] if "6177" in e.get("id", "") or "6171" in e.get("id", "") and "esc" in e.get("id", "")])
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
