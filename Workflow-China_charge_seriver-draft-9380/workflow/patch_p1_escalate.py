#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 #3: INSUFFICIENT 无逃生口 -> count>=3 转人工。

根因: #8-c 根治移除 6250b-judge 的 FALLBACK(count>=2 强制录入)解决"写垃圾记录",
      但未提供替代逃生口。INSUFFICIENT 无限递增, 用户反复补充仍不足时无限循环
      (可 ABANDON, 但无自动转人工)。

业务: 用户补充 3 次仍 INSUFFICIENT, 说明问题复杂/用户表达不清, 应转人工而非
      继续机械引导或写低质量记录。mirror 6162-abort/6162-out(ABANDON 结束)模式:
      6250b-judge 加 ESCALATE(count>=3) -> 6250b-if escalate case
      -> 6250b-escalate-abort(reset IDLE+清cv) -> 6250b-escalate-out(转人工话术+cancel)
      -> 6098(answer)。改 draft+published。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_p1_escalate.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_p1_escalate.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

NEW_6250B_JUDGE_CODE = r'''def main(llm_text: str, clarify_count) -> dict:
    import re
    text = llm_text or ""
    t = text.upper()
    if "INSUFFICIENT" in t or "NOT SUFFICIENT" in t:
        is_suf = False
    elif "SUFFICIENT" in t:
        is_suf = True
    else:
        is_suf = False
    try:
        count = int(clarify_count or 0)
    except Exception:
        count = 0
    if is_suf:
        return {"label": "SUFFICIENT", "next_count": count}
    if count >= 3:
        return {"label": "ESCALATE", "next_count": count}
    return {"label": "INSUFFICIENT", "next_count": count + 1}'''

ESCALATE_CASE = {
    "case_id": "escalate",
    "logical_operator": "and",
    "conditions": [{"comparison_operator": "is", "id": "c_esc_6250b", "value": "ESCALATE",
                    "varType": "string", "variable_selector": ["6250b-judge", "label"]}],
}

ESCALATE_ABORT = {
    "id": "6250b-escalate-abort", "type": "custom",
    "position": {"x": 920, "y": 700}, "positionAbsolute": {"x": 920, "y": 700},
    "width": 242, "height": 88, "selected": False,
    "data": {"type": "assigner", "version": "2", "title": "var_转人工reset IDLE", "selected": False,
             "items": [
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_idle"], "variable_selector": ["conversation", "cv_flow_state"]},
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_feedback_zh"]},
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_record_id"]},
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_mokuai"]},
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_huanjing"]},
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_leixing"]},
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "str_empty"], "variable_selector": ["conversation", "cv_search_keyword"]},
                 {"input_type": "variable", "operation": "over-write", "value": ["6901", "clarify_count_0"], "variable_selector": ["conversation", "cv_clarify_count"]},
             ]}
}

ESCALATE_OUT_CODE = r'''def main() -> dict:
    text = "您的问题比较复杂,为更好帮您处理,我帮您转接人工客服跟进,稍后会有专人与您联系哦~"
    return {"answer_text": text + "\n<!--SYS:TIMER|action=cancel-->\n<!--SYS:SWITCH_TO_KB_DONE-->"}'''

ESCALATE_OUT = {
    "id": "6250b-escalate-out", "type": "custom",
    "position": {"x": 1180, "y": 700}, "positionAbsolute": {"x": 1180, "y": 700},
    "width": 242, "height": 88, "selected": False,
    "data": {"type": "code", "title": "转人工话术", "code_language": "python3", "selected": False,
             "code": ESCALATE_OUT_CODE,
             "outputs": {"answer_text": {"children": None, "type": "string"}},
             "variables": []}
}


def patch_graph(g):
    nodes = g["nodes"]; edges = g["edges"]
    touched = []
    # 动态取 assigner 出边 sourceHandle (参考 6162-abort)
    abort_sh = "source"
    for e in edges:
        if e.get("source") == "6162-abort":
            abort_sh = e.get("sourceHandle", "source"); break
    if not APPLY:
        print("  [fmt] assigner sourceHandle=%r" % abort_sh)

    for n in nodes:
        if n.get("id") == "6250b-judge":
            n["data"]["code"] = NEW_6250B_JUDGE_CODE
            touched.append("6250b-judge:+ESCALATE(count>=3)")
        if n.get("id") == "6250b-if":
            cases = n["data"].get("cases", [])
            if not any(c.get("case_id") == "escalate" for c in cases):
                ins_idx = next((i for i, c in enumerate(cases) if c.get("case_id") == "insufficient"), None)
                if ins_idx is not None:
                    cases.insert(ins_idx + 1, json.loads(json.dumps(ESCALATE_CASE)))
                    touched.append("6250b-if:+escalate case")
    # 加节点
    if not any(n.get("id") == "6250b-escalate-abort" for n in nodes):
        nodes.append(json.loads(json.dumps(ESCALATE_ABORT)))
        nodes.append(json.loads(json.dumps(ESCALATE_OUT)))
        touched.append("+nodes 6250b-escalate-abort/out")
    # 加边: 6250b-if(escalate)->abort->out->6098
    e1 = {"id": "e-6250bif-esc-abort", "source": "6250b-if", "sourceHandle": "escalate",
          "target": "6250b-escalate-abort", "targetHandle": "target", "type": "custom"}
    e2 = {"id": "e-6250bescabort-out", "source": "6250b-escalate-abort", "sourceHandle": abort_sh,
          "target": "6250b-escalate-out", "targetHandle": "target", "type": "custom"}
    # out->6098: 取 6162-out->6098 的 targetHandle
    out_th = "target"
    for e in edges:
        if e.get("source") == "6162-out" and e.get("target") == "6098":
            out_th = e.get("targetHandle", "target"); break
    e3 = {"id": "e-6250bescout-6098", "source": "6250b-escalate-out", "sourceHandle": "source",
          "target": "6098", "targetHandle": out_th, "type": "custom"}
    for e in [e1, e2, e3]:
        if not any(ed.get("id") == e["id"] for ed in edges):
            edges.append(e)
            touched.append("edge %s" % e["id"])
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
        print("  verify 6250b-escalate-abort=%s | out=%s" % ("6250b-escalate-abort" in ids, "6250b-escalate-out" in ids))
        for n in g["nodes"]:
            if n.get("id") == "6250b-judge":
                print("  verify 6250b-judge has ESCALATE:", "ESCALATE" in n["data"].get("code", ""))
            if n.get("id") == "6250b-if":
                print("  verify 6250b-if has escalate case:", any(c.get("case_id") == "escalate" for c in n["data"].get("cases", [])))
        print("  verify edges:", [e["id"] for e in g["edges"] if "6250b" in e.get("id", "") and "esc" in e.get("id", "")])
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
