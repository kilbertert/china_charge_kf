#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因 #8-c: 修 6250b FALLBACK 写"待确认"垃圾进飞书。

问题: 6250b-judge 当 INSUFFICIENT 且 count>=2 返回 FALLBACK(兜底,避免无限引导)。
      6250b-parse 对 FALLBACK 返回全"待确认" -> 经 cv 写飞书(模块/操作描述/环境/类型
      全"待确认",人工无法理解)+ "待确认"作为 mokuai 进搜索(0命中垃圾查询)。
修复: 6250b-parse FALLBACK 分支返回有意义兜底内容(模块="待人工核实",
      操作描述="用户多次补充后信息仍不完整,需人工跟进核实具体问题"),人工可识别。
      根治(FALLBACK 不写表走结束话术)需改图加节点,延后。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_8c.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_8c.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

NEW_6250B_PARSE_CODE = r'''def main(llm_text: str, label: str) -> dict:
    import json, re
    if label == "FALLBACK":
        return {"mokuai":"待人工核实","caozuomiaoshu":"用户多次补充后信息仍不完整,需人工跟进核实具体问题","huanjing":"待确认","leixing":"bug"}
    text = llm_text or ""
    m = re.search(r"\{[^{}]*\}", text)
    if not m:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}
    try:
        obj = json.loads(m.group(0))
        return {
            "mokuai": str(obj.get("mokuai","")).strip()[:50],
            "caozuomiaoshu": str(obj.get("caozuomiaoshu","")).strip()[:500],
            "huanjing": str(obj.get("huanjing","")).strip()[:20],
            "leixing": str(obj.get("leixing","")).strip()[:20]
        }
    except Exception:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}'''


def patch_graph(g):
    nodes = g.get("nodes", [])
    touched = []
    for n in nodes:
        if n.get("id") == "6250b-parse":
            d = n.get("data", {})
            old = d.get("code", "")
            if "待确认" in old and 'label == "FALLBACK"' in old:
                d["code"] = NEW_6250B_PARSE_CODE
                touched.append("6250b-parse:FALLBACK 待确认->待人工核实")
            elif "待人工核实" in old:
                touched.append("6250b-parse:already patched")
            else:
                touched.append("6250b-parse:OLD pattern NOT FOUND (skip)")
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
    cur.execute("SELECT id, version, graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC", (BID,))
    rows = cur.fetchall()
    print("BID=%s  published_rows=%d  APPLY=%s" % (BID, len(rows), APPLY))
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
        print("  %s version=%s -> %s" % ("patched" if APPLY else "would-patch", r["version"], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC LIMIT 1", (BID,))
        g = cur.fetchone()["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        for n in g.get("nodes", []):
            if n.get("id") == "6250b-parse":
                c = n.get("data", {}).get("code", "")
                print("  verify 6250b-parse: 待人工核实 =", "待人工核实" in c, "| no bare 待确认 fallback =", ('"mokuai":"待确认"' not in c))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
