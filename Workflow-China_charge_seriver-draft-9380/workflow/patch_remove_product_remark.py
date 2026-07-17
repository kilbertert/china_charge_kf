#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""移除 charge B(bugtrack) 工作流里所有 code 节点对飞书字段 "产品备注" 的赋值。

业务: 产品备注字段不需要填写, 停止写入。覆盖 add-record(6260a) 与 update-record
两个组装 fields 的 code 节点 (任意缩进的 `fields["产品备注"] = ...` 行一律移除)。

幂等: 已无 "产品备注" 的节点不动; 可重复运行。

运行(在 docker-api-1 容器内, 通过 stdin 管道):
  ssh 124 'docker exec -i docker-api-1 python3 -'              < patch_remove_product_remark.py   # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'      < patch_remove_product_remark.py   # 部署
改完重启 docker-api-1 + docker-worker-1。
"""
import os, json, sys, re
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"  # charge_charging_B_bugtrack
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 匹配任意缩进的 `fields["产品备注"] = ...` 整行(含换行), 一并移除
REMARK_RE = re.compile(r'^[ \t]*fields\["产品备注"\]\s*=.*?\n', re.MULTILINE)


def strip_remark(code: str) -> str:
    return REMARK_RE.sub("", code)


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
    changed = 0
    for r in rows:
        g = r["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        nodes = g.get("nodes", [])
        touched_nodes = []
        for n in nodes:
            data = n.get("data") or {}
            code = data.get("code", "")
            if not isinstance(code, str) or "产品备注" not in code:
                continue
            new_code = strip_remark(code)
            if new_code != code:
                data["code"] = new_code  # 不可变: 重新赋值 data dict
                touched_nodes.append(n.get("id"))
        if not touched_nodes:
            print("  version=%s (no 产品备注 change)" % r["version"])
            continue
        print("  version=%s stripped nodes=%s" % (r["version"], touched_nodes))
        if APPLY:
            cur.execute(
                "UPDATE workflows SET graph=%s WHERE id=%s",
                (json.dumps(g, ensure_ascii=False), r["id"]),
            )
            changed += cur.rowcount
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
    else:
        print("\n[DRY-RUN] no DB writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
