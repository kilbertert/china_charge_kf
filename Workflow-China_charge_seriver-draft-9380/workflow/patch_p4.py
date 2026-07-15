#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4: BUG_NEW_TOPIC全覆盖 + switch-kb过渡话术 + 6177-parse raw_decode。

根因(第五轮P2-6-reg退化):
  P2补丁只给6170b/6171b(await_confirm_identity)加BUG_NEW_TOPIC, 未同步到6170/6170c/6170d/6171/6171c/6171d。
  用户在await_confirm_new/await_diff_decision/await_confirm_modify态报告新bug, 被判IRRELEVANT->6162->SWITCH_TO_KB_REENTRY(切KB,空回复)。
  6162-switch-kb只输出SWITCH marker无用户话术(Issue2空回复)。
  6177-parse仍用re.search正则不支持嵌套JSON(发现3)。

业务: 用户在任何待确认态报告新bug(不同问题), 应进bug流程(reset cv+6250), 而非误切KB。
      switch-kb应给用户过渡话术(不空回复)。JSON解析应支持嵌套。

修复:
  1. 6170/6170c/6170d prompt加BUG_NEW_TOPIC标签(细分IRRELEVANT: 新bug vs 真无关)
  2. 6170-parse label加BUG_NEW_TOPIC(6170经parse, 6170c/6170d不经parse直接text)
  3. 6171(var=6170-parse.label)/6171c(var=6170c.text)/6171d(var=6170d.text)加bug_new_topic case -> 6171b-bug-reset(复用) -> 6250
  4. 6162-switch-kb/6239-switch-kb加过渡话术("正在为您切换到智能问答服务,稍等~")
  5. 6177-parse raw_decode(支持嵌套JSON)

改draft+published。
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 1. 6170 prompt BUG_NEW_TOPIC
P6170_OLD = "- IRRELEVANT        : 开新话题/与待确认事项无关(如查计费规则/怎么操作等非反馈类)"
P6170_NEW = ("- BUG_NEW_TOPIC    : 用户开了新话题且是充电桩bug/故障反馈(另一个充电桩问题/设备故障/订单问题/充电异常)\n"
             "- IRRELEVANT        : 开新话题且与充电桩bug无关(查计费规则/怎么操作等非反馈类)")

# 1. 6170c/6170d prompt BUG_NEW_TOPIC
P6170CD_OLD = "- IRRELEVANT       : 开新话题/无关"
P6170CD_NEW = ("- BUG_NEW_TOPIC    : 用户开了新话题且是充电桩bug/故障反馈(另一个充电桩问题/设备故障/订单问题/充电异常)\n"
               "- IRRELEVANT       : 开新话题且与充电桩bug无关(查计费规则/怎么操作等非反馈类)")

# 2. 6170-parse label 加 BUG_NEW_TOPIC
P6170PARSE_OLD = 'for label in ["CONFIRM_NEW", "MODIFY_NEW", "MODIFY_EXISTING", "ABANDON", "IRRELEVANT"]:'
P6170PARSE_NEW = 'for label in ["CONFIRM_NEW", "MODIFY_NEW", "MODIFY_EXISTING", "ABANDON", "BUG_NEW_TOPIC", "IRRELEVANT"]:'

# 3. bug_new_topic cases
def make_case(case_id, var_selector):
    return {"case_id": case_id, "logical_operator": "and",
            "conditions": [{"comparison_operator": "is", "id": "c_bnt_" + case_id, "value": "BUG_NEW_TOPIC",
                            "varType": "string", "variable_selector": var_selector}]}

CASES_6171 = make_case("bug_new_topic", ["6170-parse", "label"])
CASES_6171C = make_case("bug_new_topic", ["6170c", "text"])
CASES_6171D = make_case("bug_new_topic", ["6170d", "text"])

# 4. switch-kb 话术
SWITCH_OLD_CODE = 'return {"answer_text": "<!--SYS:SWITCH_TO_KB_REENTRY-->"}'
SWITCH_NEW_CODE = 'return {"answer_text": "正在为您切换到智能问答服务,稍等~\\n<!--SYS:SWITCH_TO_KB_REENTRY-->"}'

# 5. 6177-parse raw_decode
NEW_6177_PARSE_CODE = r'''def main(llm_text: str) -> dict:
    import json, re
    text = llm_text or ""
    obj = None
    try:
        idx = text.find("{")
        if idx >= 0:
            obj, _ = json.JSONDecoder().raw_decode(text[idx:])
    except Exception:
        obj = None
    if not obj:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}
    return {
        "mokuai": str(obj.get("mokuai","")).strip()[:50],
        "caozuomiaoshu": str(obj.get("caozuomiaoshu","")).strip()[:500],
        "huanjing": str(obj.get("huanjing","")).strip()[:20],
        "leixing": str(obj.get("leixing","")).strip()[:20]
    }'''


def patch_graph(g):
    nodes = g["nodes"]; edges = g["edges"]
    touched = []

    def add_case(nid, case_def):
        for n in nodes:
            if n.get("id") == nid:
                cases = n["data"].get("cases", [])
                if not any(c.get("case_id") == "bug_new_topic" for c in cases):
                    # default 前插
                    di = next((i for i, c in enumerate(cases) if c.get("case_id") == "default"), len(cases))
                    cases.insert(di, json.loads(json.dumps(case_def)))
                    touched.append("%s:+bug_new_topic case" % nid)
                return

    def add_edge(nid):
        eid = "e-%s-bnt-bugreset" % nid
        if not any(e.get("id") == eid for e in edges):
            edges.append({"id": eid, "source": nid, "sourceHandle": "bug_new_topic",
                          "target": "6171b-bug-reset", "targetHandle": "target", "type": "custom"})
            touched.append("edge %s[bug_new_topic]->6171b-bug-reset" % nid)

    for n in nodes:
        nid = n.get("id"); d = n.get("data", {})
        # 1. 6170/6170c/6170d prompt
        if nid == "6170":
            txt = d.get("prompt_template", [{}])[0].get("text", "")
            if P6170_OLD in txt and "BUG_NEW_TOPIC" not in txt:
                d["prompt_template"][0]["text"] = txt.replace(P6170_OLD, P6170_NEW, 1)
                touched.append("6170:+BUG_NEW_TOPIC")
        if nid in ("6170c", "6170d"):
            txt = d.get("prompt_template", [{}])[0].get("text", "")
            if P6170CD_OLD in txt and "BUG_NEW_TOPIC" not in txt:
                d["prompt_template"][0]["text"] = txt.replace(P6170CD_OLD, P6170CD_NEW, 1)
                touched.append("%s:+BUG_NEW_TOPIC" % nid)
        # 2. 6170-parse label
        if nid == "6170-parse":
            code = d.get("code", "")
            if P6170PARSE_OLD in code and "BUG_NEW_TOPIC" not in code:
                d["code"] = code.replace(P6170PARSE_OLD, P6170PARSE_NEW, 1)
                touched.append("6170-parse:+BUG_NEW_TOPIC label")
        # 3. 6171/6171c/6171d case
        if nid == "6171":
            add_case("6171", CASES_6171)
        if nid == "6171c":
            add_case("6171c", CASES_6171C)
        if nid == "6171d":
            add_case("6171d", CASES_6171D)
        # 4. switch-kb 话术
        if nid in ("6162-switch-kb", "6239-switch-kb"):
            code = d.get("code", "")
            if SWITCH_OLD_CODE in code:
                d["code"] = code.replace(SWITCH_OLD_CODE, SWITCH_NEW_CODE, 1)
                touched.append("%s:+过渡话术" % nid)
        # 5. 6177-parse raw_decode
        if nid == "6177-parse":
            d["code"] = NEW_6177_PARSE_CODE
            touched.append("6177-parse:raw_decode")

    # 3. 边 6171/6171c/6171d[bug_new_topic]->6171b-bug-reset
    add_edge("6171")
    add_edge("6171c")
    add_edge("6171d")
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
    print("rows=%d APPLY=%s" % (len(rows), APPLY))
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
        print("\n[APPLIED] %d rows" % changed)
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s ORDER BY updated_at DESC LIMIT 1", (BID,))
        g = json.loads(cur.fetchone()["graph"])
        for n in g["nodes"]:
            if n.get("id") in ("6170","6170c","6170d"):
                print("  %s BUG_NEW_TOPIC: %s" % (n["id"], "BUG_NEW_TOPIC" in n["data"]["prompt_template"][0]["text"]))
            if n.get("id") == "6170-parse":
                print("  6170-parse BUG_NEW_TOPIC:", "BUG_NEW_TOPIC" in n["data"].get("code",""))
            if n.get("id") in ("6171","6171c","6171d"):
                cs = [c.get("case_id") for c in n["data"].get("cases",[])]
                print("  %s cases: %s" % (n["id"], cs))
            if n.get("id") == "6162-switch-kb":
                print("  6162-switch-kb has 话术:", "切换到智能问答" in n["data"].get("code",""))
            if n.get("id") == "6177-parse":
                print("  6177-parse raw_decode:", "raw_decode" in n["data"].get("code",""))
        for e in g["edges"]:
            if "bnt" in e.get("id",""):
                print("  edge %s -> %s" % (e.get("id"), e.get("target")))
    else:
        print("\n[DRY-RUN]")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
