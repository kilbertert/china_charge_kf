#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 charge B 截图结构化与飞书查重请求契约。

只修改当前 effective published + draft：
1. N5/N5b 开启 sys.files vision，保证截图直接进入结构化节点；
2. 6240build 同时发送 keyword/module/op_desc，供 Bug API 多字段召回与相似度排序。

运行（docker-api-1 容器内，通过 stdin 管道）：
  docker exec -i docker-api-1 python3 - < patch_bugtrack_image_search.py
  docker exec -i docker-api-1 python3 - --apply < patch_bugtrack_image_search.py
"""

import json
import os
import sys

import psycopg2
import psycopg2.extras


BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = len(sys.argv) > 1 and sys.argv[1] == "--apply"

VISION = {
    "configs": {"detail": "high", "variable_selector": ["sys", "files"]},
    "enabled": True,
}
BUILD_CODE = '''def main(mokuai: str, search_keyword: str, op_desc: str) -> dict:
    import json
    module = (mokuai or "").strip()
    keyword = (search_keyword or "").strip() or module
    payload = {"keyword": keyword, "module": module, "op_desc": (op_desc or "").strip(), "limit": 5}
    return {"body_json": json.dumps(payload, ensure_ascii=False)}'''
OP_DESC_VAR = {
    "variable": "op_desc",
    "value_selector": ["conversation", "cv_feedback_zh"],
}


def _patch_prompt(data: dict, prompt_id: str, replacements: list[tuple[str, str]]) -> bool:
    for prompt in data.get("prompt_template") or []:
        if prompt.get("id") != prompt_id:
            continue
        old_text = prompt.get("text") or ""
        new_text = old_text
        for old, new in replacements:
            if new not in new_text:
                new_text = new_text.replace(old, new)
        if new_text != old_text:
            prompt["text"] = new_text
            return True
    return False


def mutate(graph: dict) -> tuple[dict, list[str]] | None:
    touched: list[str] = []
    for node in graph.get("nodes", []):
        node_id = str(node.get("id", ""))
        data = node.get("data") or {}
        changed = False

        if node_id in {"6250", "6250b"} and data.get("vision") != VISION:
            data["vision"] = json.loads(json.dumps(VISION))
            changed = True

        if node_id == "6250":
            changed = _patch_prompt(
                data,
                "n5-sys",
                [
                    (
                        "【输入】用户反馈: {{#6002.query_text#}}",
                        "【输入】用户反馈文本: {{#6002.query_text#}}\n\n"
                        "用户附带截图时,必须同时读取 sys.files 中的图片内容,"
                        "把截图里的页面、标签、报错和异常现象纳入四字段与查重词提取。",
                    ),
                    (
                        "- 100%基于输入文本,不脑补不编造",
                        "- 100%基于输入文本与用户截图,不脑补不编造",
                    ),
                ],
            ) or changed

        if node_id == "6250b":
            changed = _patch_prompt(
                data,
                "n5b-sys",
                [
                    (
                        "【当前用户补充】: {{#6002.query_text#}}",
                        "【当前用户补充】: {{#6002.query_text#}}\n\n"
                        "用户本轮附带截图时,必须同时读取 sys.files 中的图片内容"
                        "并合并到结构化字段。",
                    ),
                    (
                        "- 100%基于输入文本,不脑补不编造",
                        "- 100%基于输入文本、历史字段与用户截图,不脑补不编造",
                    ),
                ],
            ) or changed

        if node_id == "6240build":
            if data.get("code") != BUILD_CODE:
                data["code"] = BUILD_CODE
                changed = True
            variables = data.get("variables") or []
            if not any(
                isinstance(item, dict) and item.get("variable") == "op_desc"
                for item in variables
            ):
                data["variables"] = variables + [dict(OP_DESC_VAR)]
                changed = True

        if changed:
            touched.append(node_id)

    if not touched:
        return None
    return graph, touched


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
            cur.execute("SELECT workflow_id FROM apps WHERE id=%s", (BID,))
            effective = cur.fetchone()
            if not effective or not effective["workflow_id"]:
                print("charge B 未找到 effective workflow")
                return

            cur.execute(
                "SELECT id FROM workflows WHERE app_id=%s AND version='draft'",
                (BID,),
            )
            draft = cur.fetchone()
            targets = [(effective["workflow_id"], "published(effective)")]
            if draft and draft["id"] != effective["workflow_id"]:
                targets.append((draft["id"], "draft"))

            print(
                f"[patch] app={BID[:8]} apply={APPLY} "
                f"targets={[(wid[:8], kind) for wid, kind in targets]}"
            )
            for workflow_id, kind in targets:
                cur.execute("SELECT graph FROM workflows WHERE id=%s", (workflow_id,))
                graph = cur.fetchone()["graph"]
                if isinstance(graph, str):
                    graph = json.loads(graph)
                result = mutate(graph)
                if result is None:
                    print(f"  skip {workflow_id[:8]} ({kind}) - already current")
                    continue
                new_graph, touched = result
                print(
                    f"  {'UPDATED' if APPLY else 'DRY-RUN would update'} "
                    f"{workflow_id[:8]} ({kind}) nodes={touched}"
                )
                if APPLY:
                    cur.execute(
                        "UPDATE workflows SET graph=%s WHERE id=%s",
                        (json.dumps(new_graph, ensure_ascii=False), workflow_id),
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
