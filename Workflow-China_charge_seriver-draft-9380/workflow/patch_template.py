#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch 模板 (⑩ 规范): 只改 latest published + draft, 保留版本历史。

运行 (docker-api-1 容器内, 复用 Dify DB env):
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_template.py   # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_template.py   # 部署

== ⑩ 规范 (只改 latest published, 保留版本历史) ==
  - apps.workflow_id 指向【当前生效的 published】版本 — 生产 API 实际调用此版本。
    改它 = patch 立即生产生效。
  - 同时改 draft — 防 UI 重新发布时从旧 draft 复制出新 published, 丢 patch
    (P0-1 教训: patch_memory 只改 published 不改 draft, 7/11 UI 发布后 memory 全丢)。
  - 不动旧 published — 保留版本历史, 便于回滚/审计。

== 反模式 (勿用) ==
  - `WHERE app_id=%s ORDER BY updated_at DESC` (无 version!='draft'): 可能选到 draft 当生产版
  - 遍历所有 published 全改 (`for r in rows: UPDATE`): 污染历史版本, 无法回滚
  - 只改 published 不改 draft: UI 一旦重新发布, patch 丢失
"""
import os
import json
import sys

import psycopg2
import psycopg2.extras

APP_ID = "707dd6d2-059f-47c9-aaac-4638e74969c6"  # 改成目标 app id
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")


def mutate(g: dict) -> dict | None:
    """改 graph dict, 返回新 graph; 返回 None 跳过该版本。

    在下方写你的改动 (示例: 修改某节点 text)。
    """
    # for n in g["nodes"]:
    #     if n["id"] == "6xxx":
    #         n["data"]["text"] = "新内容"
    #         return g
    return None  # 占位: 默认跳过; 实现你的改动后 return g


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
            # 1. 当前生效 published (apps.workflow_id) — 生产 API 调用此版本
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
                g = cur.fetchone()["graph"]
                if isinstance(g, str):
                    g = json.loads(g)

                new_g = mutate(g)
                if new_g is None:
                    print(f"  skip {wid[:8]} ({kind})")
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
