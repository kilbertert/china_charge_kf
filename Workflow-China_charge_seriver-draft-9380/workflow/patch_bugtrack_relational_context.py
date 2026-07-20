#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 charge B 的 search/add/update 请求补充关系型草稿上下文。

只修改 apps.workflow_id 指向的 effective published 与 draft，保留历史 published。
默认 dry-run；传 ``--apply`` 才写 Dify PostgreSQL。
"""

from __future__ import annotations

import json
import os
import sys

import psycopg2
import psycopg2.extras


APP_ID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = len(sys.argv) > 1 and sys.argv[1] == "--apply"

SEARCH_CODE = r'''def main(mokuai: str, search_keyword: str, op_desc: str, conversation_id: str, flow_state: str, query_text: str) -> dict:
    import hashlib, json
    module = (mokuai or "").strip()
    keyword = (search_keyword or "").strip() or module
    conv = (conversation_id or "").strip()
    state = (flow_state or "IDLE").strip()
    query = (query_text or "").strip()
    idem_raw = "|".join([conv, state, query, keyword, module])
    payload = {"keyword": keyword, "module": module, "op_desc": (op_desc or "").strip(), "limit": 5, "conversation_id": conv, "flow_state": state, "source_text": query, "force_new": state == "IDLE", "idempotency_key": "dify-search-" + hashlib.sha256(idem_raw.encode("utf-8")).hexdigest()}
    return {"body_json": json.dumps(payload, ensure_ascii=False)}'''

ADD_CODE = r'''def main(mokuai: str, caozuomiaoshu: str, huanjing: str, leixing: str, conversation_id: str, flow_state: str, query_text: str) -> dict:
    import hashlib, json
    fields = {}
    if mokuai:
        fields["模块/功能点"] = mokuai[:100]
    if caozuomiaoshu:
        fields["操作描述"] = caozuomiaoshu[:2000]
    if huanjing and huanjing in ("后台", "管家端", "用户端"):
        fields["环境"] = huanjing
    fields["类型"] = (leixing or "bug")[:10]
    fields["问题状态"] = "问题未查阅"
    conv = (conversation_id or "").strip()
    query = (query_text or "").strip()
    body = {"fields": fields, "conversation_id": conv, "flow_state": (flow_state or "").strip(), "source_text": query, "idempotency_key": "dify-add-" + hashlib.sha256((conv + "|" + query).encode("utf-8")).hexdigest()}
    return {"body_json": json.dumps(body, ensure_ascii=False)}'''

UPDATE_CODE = r'''def main(record_id: str, feedback_zh: str, mokuai: str, huanjing: str, leixing: str, conversation_id: str, flow_state: str, query_text: str) -> dict:
    import hashlib, json
    fields = {}
    if mokuai:
        fields["模块/功能点"] = mokuai[:100]
    if feedback_zh:
        fields["操作描述"] = feedback_zh[:2000]
    if huanjing and huanjing in ("后台", "管家端", "用户端"):
        fields["环境"] = huanjing
    fields["类型"] = (leixing or "bug")[:10]
    conv = (conversation_id or "").strip()
    query = (query_text or "").strip()
    body = {"record_id": record_id, "fields": fields, "conversation_id": conv, "flow_state": (flow_state or "").strip(), "source_text": query, "idempotency_key": "dify-update-" + hashlib.sha256((conv + "|" + str(record_id) + "|" + query).encode("utf-8")).hexdigest()}
    return {"body_json": json.dumps(body, ensure_ascii=False)}'''

EXTRA_VARS = [
    {"variable": "conversation_id", "value_selector": ["sys", "conversation_id"]},
    {"variable": "flow_state", "value_selector": ["conversation", "cv_flow_state"]},
    {"variable": "query_text", "value_selector": ["6002", "query_text"]},
]


def _set_node(graph: dict, node_id: str, code: str) -> bool:
    for node in graph.get("nodes", []):
        if str(node.get("id")) != node_id:
            continue
        data = node.get("data") or {}
        changed = data.get("code") != code
        data["code"] = code
        variables = list(data.get("variables") or [])
        present = {item.get("variable") for item in variables if isinstance(item, dict)}
        for item in EXTRA_VARS:
            if item["variable"] not in present:
                variables.append(dict(item))
                changed = True
        data["variables"] = variables
        return changed
    raise RuntimeError(f"node {node_id} not found")


def mutate(graph: dict) -> tuple[dict, list[str]]:
    changed: list[str] = []
    for node_id, code in (
        ("6240build", SEARCH_CODE),
        ("6260a", ADD_CODE),
        ("6176a", UPDATE_CODE),
    ):
        if _set_node(graph, node_id, code):
            changed.append(node_id)
    return graph, changed


def main() -> None:
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("SELECT workflow_id FROM apps WHERE id=%s", (APP_ID,))
            effective = cursor.fetchone()
            if not effective or not effective["workflow_id"]:
                raise RuntimeError("effective workflow not found")
            cursor.execute(
                "SELECT id FROM workflows WHERE app_id=%s AND version='draft'",
                (APP_ID,),
            )
            draft = cursor.fetchone()
            targets = [(effective["workflow_id"], "published(effective)")]
            if draft and draft["id"] != effective["workflow_id"]:
                targets.append((draft["id"], "draft"))
            print(f"[patch] apply={APPLY} targets={[(x[:8], k) for x, k in targets]}")
            for workflow_id, kind in targets:
                cursor.execute("SELECT graph FROM workflows WHERE id=%s", (workflow_id,))
                graph = cursor.fetchone()["graph"]
                if isinstance(graph, str):
                    graph = json.loads(graph)
                graph, changed = mutate(graph)
                print(f"  {workflow_id[:8]} {kind}: changed={changed or 'none'}")
                if APPLY and changed:
                    cursor.execute(
                        "UPDATE workflows SET graph=%s WHERE id=%s",
                        (json.dumps(graph, ensure_ascii=False), workflow_id),
                    )
        if APPLY:
            conn.commit()
            print("[patch] committed")
        else:
            print("[patch] dry-run")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

