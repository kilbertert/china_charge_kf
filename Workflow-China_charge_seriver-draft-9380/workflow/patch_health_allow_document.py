#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""允许 health_consult 工作流 start 节点 input_image 接受 document 类型 (P1-2 PDF 闭环)。

背景: start 节点 input_image 的 allowed_file_extensions 已含 .pdf, 但 allowed_file_types
仅 [image] -> Dify 按 type 过滤, document(PDF) 被拒。后端 ⑧ 已把 PDF 标 document 上传,
工作流侧必须放行 document 才能 PDF 端到端。

规范 (⑩): 只改当前生效 published (apps.workflow_id) + draft, 不动旧 published (保留版本历史)。
运行 (docker-api-1 容器内, 复用 Dify DB env):
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_health_allow_document.py   # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_health_allow_document.py   # 部署
改完重启 docker-api-1 + docker-worker-1。
"""
import os
import json
import sys

import psycopg2
import psycopg2.extras

# health_consult app: AI_health_consultant_v2 (生效 workflow 0df13d34...)
APP_ID = "d5e87520-a838-4c72-92cc-8b00eaa81382"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")


def mutate(g: dict) -> dict | None:
    """start 节点 input_image 变量 allowed_file_types 加 document。返回新 graph; None 跳过。"""
    changed = False
    for n in g.get("nodes", []):
        data = n.get("data") or {}
        if data.get("type") != "start":
            continue
        for v in data.get("variables") or []:
            if v.get("variable") != "input_image":
                continue
            types = v.get("allowed_file_types") or []
            if "document" in types:
                continue  # 已放行, 幂等
            # 不可变: 重建 list
            v["allowed_file_types"] = types + ["document"]
            changed = True
            print(f"  node={n.get('id')} input_image: allowed_file_types {types} -> {v['allowed_file_types']}")
    return g if changed else None


def main() -> None:
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. 当前生效 published (apps.workflow_id)
            cur.execute("SELECT workflow_id FROM apps WHERE id=%s", (APP_ID,))
            eff = cur.fetchone()
            if not eff or not eff["workflow_id"]:
                print(f"app {APP_ID[:8]} 无 workflow_id (未发布?)")
                return
            eff_id = eff["workflow_id"]

            # 2. draft (防 UI 重新发布丢 patch)
            cur.execute(
                "SELECT id FROM workflows WHERE app_id=%s AND version='draft'",
                (APP_ID,),
            )
            draft = cur.fetchone()

            targets = [(eff_id, "published(effective)")]
            if draft and draft["id"] != eff_id:
                targets.append((draft["id"], "draft"))

            print(f"[patch] app={APP_ID[:8]} apply={APPLY} "
                  f"targets={[(t[0][:8], t[1]) for t in targets]}")

            for wid, kind in targets:
                cur.execute("SELECT graph FROM workflows WHERE id=%s", (wid,))
                row = cur.fetchone()
                g = row["graph"]
                if isinstance(g, str):
                    g = json.loads(g)

                new_g = mutate(g)
                if new_g is None:
                    print(f"  skip {wid[:8]} ({kind}) - input_image already allows document")
                    continue

                if APPLY:
                    cur.execute(
                        "UPDATE workflows SET graph=%s WHERE id=%s",
                        (json.dumps(new_g, ensure_ascii=False), wid),
                    )
                    print(f"  UPDATED {wid[:8]} ({kind})")
                else:
                    print(f"  DRY-RUN would update {wid[:8]} ({kind})")
        if APPLY:
            conn.commit()
            print("[patch] committed")
        else:
            print("[patch] dry-run (no write); pass --apply to deploy")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
