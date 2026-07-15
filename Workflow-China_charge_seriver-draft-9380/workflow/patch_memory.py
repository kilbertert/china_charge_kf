#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因1: 给 A/B 的分类器节点开 memory 块,修复多轮记忆断裂。

Dify 1.14.2 MemoryConfig schema (graphon/prompt_entities.py:23):
  memory: { window: {enabled: bool, size: int},        # 必填
            role_prefix?: {user:str, assistant:str},    # 可选,仅 completion 模式
            query_prompt_template?: str }               # 可选
llm 节点和 question-classifier 节点都支持 memory,会把历史注入 prompt(question-classifier 注入 <histories>)。

本次范围 = 7 个分类器(它们判"是的/对/不是"等短回复时需要看到 bot 上一轮问什么):
  A: 6101 (L1 板块路由, question-classifier), 6201 (L3 意图, question-classifier)
  B: 6170, 6170b, 6170c, 6170d (N17 系列, llm), 6239-llm (修改窗意图, llm)
window.size=10 (最近 10 条消息 ≈ 5 轮)。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_memory.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_memory.py        # 部署
部署后需重启 docker-api-1 + docker-worker-1。
"""
import os, json, sys
import psycopg2, psycopg2.extras

APPS = {
    "A": ("33fde774-aeed-4026-a7f7-a0e339e1c030", ["6101", "6201"]),
    "B": ("707dd6d2-059f-47c9-aaac-4638e74969c6", ["6170", "6170b", "6170c", "6170d", "6239-llm"]),
}
MEMORY = {"window": {"enabled": True, "size": 10}}
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")


def main():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    total = 0
    for label, (aid, ids) in APPS.items():
        cur.execute(
            "SELECT id, version, graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC",
            (aid,),
        )
        rows = cur.fetchall()
        print("=== APP %s id=%s published_rows=%d targets=%s ===" % (label, aid, len(rows), ids))
        for r in rows:
            g = r["graph"]
            if isinstance(g, str):
                g = json.loads(g)
            touched = []
            for n in g.get("nodes", []):
                if n.get("id") in ids:
                    had = "memory" in n.get("data", {})
                    n["data"]["memory"] = MEMORY
                    touched.append((n["id"], n.get("data", {}).get("type"), had))
            if not touched:
                continue
            if APPLY:
                cur.execute("UPDATE workflows SET graph=%s WHERE id=%s", (json.dumps(g, ensure_ascii=False), r["id"]))
                total += cur.rowcount
            print("  %s version=%s -> %s" % ("patched" if APPLY else "would-patch", r["version"], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] total %d rows updated" % total)
        for label, (aid, ids) in APPS.items():
            cur.execute("SELECT graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC LIMIT 1", (aid,))
            g = cur.fetchone()["graph"]
            if isinstance(g, str):
                g = json.loads(g)
            for n in g.get("nodes", []):
                if n.get("id") in ids:
                    print("  verify %s %s (%s): memory=%s" % (label, n["id"], n.get("data", {}).get("type"), n.get("data", {}).get("memory")))
    else:
        print("\n[DRY-RUN] no writes. memory to add = %s" % json.dumps(MEMORY, ensure_ascii=False))
        print("Re-run with --apply to deploy (then restart docker-api-1 + docker-worker-1).")
    cur.close()
    conn.close()


main()
