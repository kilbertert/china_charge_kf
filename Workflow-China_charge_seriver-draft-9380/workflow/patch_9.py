#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因 #9: 删 Dify 3 个 HTTP 节点的硬编码 Authorization header (token 移除)。

配合 120 后端 /internal/bugtrack/* 改 IP 白名单鉴权 (BUGTRACK_ALLOWED_IPS),
Dify 侧不再携带 Bearer token。旧 token rTlcyp8... 作废。

目标节点: 6240(D2查表) / 6260b(N16新增写表) / 6176b(N14修改写表)。
改动: data.headers 去掉 Authorization:Bearer xxx, 仅保留 Content-Type:application/json。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_9.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_9.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")
TARGETS = ["6240", "6260b", "6176b"]
CT = "Content-Type:application/json"


def patch_graph(g):
    touched = []
    for n in g.get("nodes", []):
        if n.get("id") in TARGETS:
            d = n.get("data", {})
            h = d.get("headers", "")
            if not isinstance(h, str):
                continue
            if "Authorization" in h:
                d["headers"] = CT
                touched.append("%s:strip Authorization" % n["id"])
            else:
                touched.append("%s:no Authorization (skip)" % n["id"])
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
            if n.get("id") in TARGETS:
                h = n.get("data", {}).get("headers", "")
                print("  verify %s headers=%r | has Authorization=%s" % (n["id"], h[:50], "Authorization" in h))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
