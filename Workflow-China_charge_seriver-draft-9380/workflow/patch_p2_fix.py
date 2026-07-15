#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修 P2 case variable_selector: 6170/6170b 是 LLM 输出 text 非 label。
6171 escalate case + 6171b bug_new_topic case variable_selector label->text。
(patch_p2 首次 apply 用了 label, 此 fix 修正已部署的 124 graph + 本地 yml)"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")


def patch_graph(g):
    touched = []
    for n in g.get("nodes", []):
        if n.get("id") == "6171":
            for cs in n.get("data", {}).get("cases", []):
                if cs.get("case_id") == "escalate":
                    for cond in cs.get("conditions", []):
                        if cond.get("variable_selector") == ["6170", "label"]:
                            cond["variable_selector"] = ["6170", "text"]
                            touched.append("6171:escalate var label->text")
        if n.get("id") == "6171b":
            for cs in n.get("data", {}).get("cases", []):
                if cs.get("case_id") == "bug_new_topic":
                    for cond in cs.get("conditions", []):
                        if cond.get("variable_selector") == ["6170b", "label"]:
                            cond["variable_selector"] = ["6170b", "text"]
                            touched.append("6171b:bug_new_topic var label->text")
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
            if n.get("id") == "6171":
                for cs in n["data"].get("cases", []):
                    if cs.get("case_id") == "escalate":
                        print("  6171 escalate var_selector:", cs["conditions"][0].get("variable_selector"))
            if n.get("id") == "6171b":
                for cs in n["data"].get("cases", []):
                    if cs.get("case_id") == "bug_new_topic":
                        print("  6171b bug_new_topic var_selector:", cs["conditions"][0].get("variable_selector"))
    else:
        print("\n[DRY-RUN]")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
