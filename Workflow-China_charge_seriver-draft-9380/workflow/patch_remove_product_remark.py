#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""移除 charge B(bugtrack) 工作流里所有 code 节点对飞书字段 "产品备注" 的赋值。

业务: 产品备注字段不需要填写, 停止写入。覆盖 add-record(6260a) 与 update-record
两个组装 fields 的 code 节点 (任意缩进的 `fields["产品备注"] = ...` 行一律移除)。

幂等: 已无 "产品备注" 的节点不动; 可重复运行。

== ⑩ 规范 (只改 latest published + draft, 保留版本历史) ==
  - apps.workflow_id 指向【当前生效的 published】版本 - 生产 API 实际调用此版本。
    改它 = patch 立即生产生效。
  - 同时改 draft - 防 UI 重新发布时从旧 draft 复制出新 published, 丢 patch。
  - 不动旧 published - 保留版本历史, 便于回滚/审计。

== 反模式 (本脚本早期版本曾犯, 已纠正) ==
  - 遍历所有 `version!='draft'` 全改: 污染历史版本, 无法回滚, 与 ⑩ 规范冲突。
    生产核查(2026-07-17): 早期版本曾以此方式执行, 674ff618(生效)+d42bf0b7(旧 published)
    被改写; 07-08 旧版未含产品备注代码未被触。d42bf0b7 已被 674ff618 取代不对外服务,
    回滚到它亦无产品备注(符合永久移除意图), 无功能危害。本脚本已改为只改 effective+draft。

运行 (在 docker-api-1 容器内, 通过 stdin 管道):
  ssh 124 'docker exec -i docker-api-1 python3 -'              < patch_remove_product_remark.py   # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'      < patch_remove_product_remark.py   # 部署
改完重启 docker-api-1 + docker-worker-1。
"""
import os
import json
import sys
import re

import psycopg2
import psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"  # charge_charging_B_bugtrack
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 匹配任意缩进的 `fields["产品备注"] = ...` 整行(含换行), 一并移除
REMARK_RE = re.compile(r'^[ \t]*fields\["产品备注"\]\s*=.*?\n', re.MULTILINE)


def strip_remark(code: str) -> str:
    return REMARK_RE.sub("", code)


def mutate(g: dict) -> tuple[dict, list] | None:
    """改 graph dict, 返回 (new_graph, touched_node_ids); 返回 None 跳过该版本。"""
    touched_nodes: list = []
    for n in g.get("nodes", []):
        data = n.get("data") or {}
        code = data.get("code", "")
        if not isinstance(code, str) or "产品备注" not in code:
            continue
        new_code = strip_remark(code)
        if new_code != code:
            data["code"] = new_code  # 重新赋值 data dict (不可变: 不原地改 code 字符串)
            touched_nodes.append(n.get("id"))
    if not touched_nodes:
        return None
    return g, touched_nodes


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
            # 1. 当前生效 published (apps.workflow_id) - 生产 API 调用此版本
            cur.execute("SELECT workflow_id FROM apps WHERE id=%s", (BID,))
            eff = cur.fetchone()
            if not eff or not eff["workflow_id"]:
                print(f"app {BID[:8]} 无 workflow_id (未发布?)")
                return
            eff_id = eff["workflow_id"]

            # 2. draft (防 UI 重新发布丢 patch)
            cur.execute(
                "SELECT id FROM workflows WHERE app_id=%s AND version='draft'",
                (BID,),
            )
            draft = cur.fetchone()

            targets = [(eff_id, "published(effective)")]
            if draft and draft["id"] != eff_id:
                targets.append((draft["id"], "draft"))

            print(f"[patch] app={BID[:8]} apply={APPLY} "
                  f"targets={[(t[0][:8], t[1]) for t in targets]}")

            for wid, kind in targets:
                cur.execute("SELECT graph FROM workflows WHERE id=%s", (wid,))
                row = cur.fetchone()
                g = row["graph"]
                if isinstance(g, str):
                    g = json.loads(g)

                result = mutate(g)
                if result is None:
                    print(f"  skip {wid[:8]} ({kind}) - no 产品备注 to strip")
                    continue
                new_g, touched = result
                print(f"  {'UPDATED' if APPLY else 'DRY-RUN would update'} "
                      f"{wid[:8]} ({kind}) stripped nodes={touched}")
                if APPLY:
                    cur.execute(
                        "UPDATE workflows SET graph=%s WHERE id=%s",
                        (json.dumps(new_g, ensure_ascii=False), wid),
                    )
        if APPLY:
            conn.commit()
            print("[patch] committed")
        else:
            print("[patch] dry-run (no write); pass --apply to deploy")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
