#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 charge B(bugtrack) 的 6260a(N16 组装飞书fields) 加 conversation_id, 让 /add
能按会话回取 bug 截图入飞书附件。

背景: 用户 bug 截图在 turn1 发出, 写表在 turn2(确认后)。WeCom 后端在 turn1 把图片
file_id 按 conversation_id 缓存(dify.py _CONV_IMAGE_CACHE), turn2 Dify 6260a 在
/internal/bugtrack/add 的 body 里带上 conversation_id, 后端 /add 按 conv_id 取缓存
图片 file_id -> fetch_upload_bytes 取字节 -> 飞书附件字段 "Bug截图"。

改动 6260a:
  1) code: main() 加 conversation_id 形参, body_json 顶层加 "conversation_id"
  2) variables: 加 {variable: conversation_id, value_selector: [sys, conversation_id]}

运行(在 docker-api-1 容器内, 通过 stdin 管道):
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_bug_screenshot_6260a.py   # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_bug_screenshot_6260a.py   # 部署
改完重启 docker-api-1 + docker-worker-1。
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"  # charge_charging_B_bugtrack
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

NEW_6260A_CODE = r'''def main(mokuai: str, caozuomiaoshu: str, huanjing: str, leixing: str, conversation_id: str) -> dict:
    import json
    fields = {}
    if mokuai:
        fields["模块/功能点"] = mokuai[:100]
    if caozuomiaoshu:
        fields["操作描述"] = caozuomiaoshu[:2000]
    if huanjing and huanjing in ("后台", "管家端", "用户端"):
        fields["环境"] = huanjing
    fields["类型"] = (leixing or "bug")[:10]
    fields["问题状态"] = "问题未查阅"
    fields["产品备注"] = (caozuomiaoshu or "")[:500]
    body = {"fields": fields}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return {"body_json": json.dumps(body, ensure_ascii=False)}'''

CONV_VAR = {"variable": "conversation_id", "value_selector": ["sys", "conversation_id"]}


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
        touched = False
        for n in nodes:
            if n.get("id") != "6260a":
                continue
            data = n.get("data") or {}
            old_code = data.get("code", "")
            # 幂等: 已含 conversation_id 形参则跳过 code 替换
            if "conversation_id: str" not in old_code:
                data["code"] = NEW_6260A_CODE
                touched = True
            # 加 conversation_id 变量 (幂等: 不重复加)
            variables = data.get("variables") or []
            has_conv = any(
                (v.get("variable") == "conversation_id")
                for v in variables if isinstance(v, dict)
            )
            if not has_conv:
                variables = variables + [dict(CONV_VAR)]  # 不可变: 新列表
                data["variables"] = variables
                touched = True
            print("  6260a code has conv param: %s | variables: %s"
                  % ("conversation_id: str" in data.get("code", ""),
                     [v.get("variable") for v in (data.get("variables") or []) if isinstance(v, dict)]))
        if not touched:
            print("  (no change needed for version=%s)" % r["version"])
            continue
        if APPLY:
            cur.execute(
                "UPDATE workflows SET graph=%s WHERE id=%s",
                (json.dumps(g, ensure_ascii=False), r["id"]),
            )
            changed += cur.rowcount
        print("  %s version=%s %s" % ("patched" if APPLY else "would-patch", r["version"], "(written)" if APPLY else ""))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
    else:
        print("\n[DRY-RUN] no DB writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
