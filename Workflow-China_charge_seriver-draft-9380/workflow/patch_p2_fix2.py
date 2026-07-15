#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 fix2: 修第三轮E2E暴露的3个遗漏(patch_p1_escalate/patch_p2 加节点+边但未注册aggregator + 6170-parse缺ESCALATE + 6171[escalate] variable_selector不一致)。

根因(第三轮E2E验证):
  1. 6098 variable-aggregator variables 缺 ['6177-deny-out','answer_text']和['6250b-escalate-out','answer_text']
     -> 6177-deny-out/6250b-escalate-out 执行产出文本但6098不聚合 -> 用户看空回复
  2. 6170-parse label列表缺ESCALATE -> 6170 LLM输出ESCALATE时6170-parse返回IRRELEVANT
  3. 6171[escalate] variable_selector=['6170','text'](patch_p2_fix改的), 其他case用['6170-parse','label'] -> 不一致+脆弱

修复:
  - 6098 variables 追加 6177-deny-out + 6250b-escalate-out
  - 6170-parse label列表加 ESCALATE
  - 6171[escalate] variable_selector ['6170','text']->['6170-parse','label']

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_p2_fix2.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_p2_fix2.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

NEW_6170_PARSE_CODE = r'''def main(llm_text: str) -> dict:
    import re
    t = (llm_text or "").upper()
    for label in ["CONFIRM_NEW", "MODIFY_NEW", "MODIFY_EXISTING", "ABANDON", "ESCALATE", "IRRELEVANT"]:
        if label in t:
            return {"label": label}
    return {"label": "IRRELEVANT"}'''


def patch_graph(g):
    touched = []
    for n in g.get("nodes", []):
        nid = n.get("id"); d = n.get("data", {})
        if nid == "6170-parse":
            d["code"] = NEW_6170_PARSE_CODE
            touched.append("6170-parse:+ESCALATE label")
        if nid == "6171":
            for cs in d.get("cases", []):
                if cs.get("case_id") == "escalate":
                    for cond in cs.get("conditions", []):
                        if cond.get("variable_selector") == ["6170", "text"]:
                            cond["variable_selector"] = ["6170-parse", "label"]
                            touched.append("6171[escalate] var 6170.text->6170-parse.label")
        if nid == "6098":
            vs = d.get("variables", [])
            if ["6177-deny-out", "answer_text"] not in vs:
                vs.append(["6177-deny-out", "answer_text"])
                touched.append("6098:+6177-deny-out")
            if ["6250b-escalate-out", "answer_text"] not in vs:
                vs.append(["6250b-escalate-out", "answer_text"])
                touched.append("6098:+6250b-escalate-out")
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
            if n.get("id") == "6098":
                vs = n["data"].get("variables", [])
                print("  6098 has 6177-deny-out:", ["6177-deny-out", "answer_text"] in vs)
                print("  6098 has 6250b-escalate-out:", ["6250b-escalate-out", "answer_text"] in vs)
            if n.get("id") == "6170-parse":
                print("  6170-parse has ESCALATE:", "ESCALATE" in n["data"].get("code", ""))
            if n.get("id") == "6171":
                for cs in n["data"].get("cases", []):
                    if cs.get("case_id") == "escalate":
                        print("  6171[escalate] var:", cs["conditions"][0].get("variable_selector"))
    else:
        print("\n[DRY-RUN]")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
