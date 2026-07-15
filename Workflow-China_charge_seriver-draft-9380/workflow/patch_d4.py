#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因3: 修 D4 命中汇报冷模板 (charge B 的 6240-parse + 6242)。

问题: 6242 只塞 raw op_desc, 丢进度 (问题状态/产品回复/完成结果), 冷且机械。
修复 (无LLM, 对齐设计"命中不用LLM"):
  - 6240-parse: 把命中行组装成客户可读正文 (所属模块/问题描述/当前状态/产品回复/完成结果)
  - 6242: 改暖 greeting "您好,这个问题我们之前已经记录在跟进中了:..."
前提: 后端 record_to_summary 已加 dev_status/reply/result 字段 (feishu_bitable.py)。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_d4.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_d4.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"  # charge_charging_B_bugtrack
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

NEW_6240_PARSE = r'''def main(http_body: str) -> dict:
    import json
    try:
        data = json.loads(http_body or "{}")
    except Exception:
        return {"hit_record_id": "", "row_summary": ""}
    hits = data.get("hits") or []
    if not hits:
        return {"hit_record_id": "", "row_summary": ""}
    h = hits[0]
    rid = h.get("record_id", "")
    module = (h.get("module") or "").strip()
    op_desc = (h.get("op_desc") or h.get("summary") or "").strip()
    dev_status = (h.get("dev_status") or "").strip()
    reply = (h.get("reply") or "").strip()
    result = (h.get("result") or "").strip()
    parts = []
    if module:
        parts.append("所属模块:" + module)
    if op_desc:
        parts.append("问题描述:" + op_desc)
    if dev_status:
        parts.append("当前状态:" + dev_status)
    if reply:
        parts.append("产品回复:" + reply)
    if result:
        parts.append("完成结果:" + result)
    row_summary = "\n".join(parts) if parts else op_desc[:500]
    return {"hit_record_id": rid, "row_summary": row_summary}'''

NEW_6242 = r'''def main(row_summary: str) -> dict:
    s = (row_summary or "").strip()
    if not s:
        s = "该记录内容"
    return {"answer_text": "您好,这个问题我们之前已经记录在跟进中了:\n" + s + "\n\n请问您这次反馈的是同一个问题吗?"}'''


def main():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, version, graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC",
        (BID,),
    )
    rows = cur.fetchall()
    print("BID=%s  published_rows=%d  APPLY=%s" % (BID, len(rows), APPLY))
    targets = {"6240-parse": NEW_6240_PARSE, "6242": NEW_6242}
    changed = 0
    for r in rows:
        g = r["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        touched = []
        for n in g.get("nodes", []):
            nid = n.get("id")
            if nid in targets:
                n["data"]["code"] = targets[nid]
                touched.append(nid)
        if not touched:
            continue
        if APPLY:
            cur.execute("UPDATE workflows SET graph=%s WHERE id=%s", (json.dumps(g, ensure_ascii=False), r["id"]))
            changed += cur.rowcount
        print("  %s version=%s nodes=%s" % ("patched" if APPLY else "would-patch", r["version"], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC LIMIT 1", (BID,))
        g = cur.fetchone()["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        for n in g.get("nodes", []):
            if n.get("id") in targets:
                code = n.get("data", {}).get("code", "")
                print("  verify %s: has '当前状态'=%s  has '跟进中'=%s" % (
                    n["id"],
                    "当前状态" in code,
                    "跟进中" in code,
                ))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
