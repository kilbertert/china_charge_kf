#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 charge B 待确认轮被“附件上传要求”误判为 MODIFY_NEW。

只修改 effective published + draft：
1. 6170-parse 用当前用户原话做确定性确认闸门；
2. N17 明确“确认 + 上传图片要求”仍为 CONFIRM_NEW；
3. N5b 禁止把完整历史字段重新判不足或声称窗口不支持图片。
"""

import json
import os
import sys

import psycopg2
import psycopg2.extras


BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = len(sys.argv) > 1 and sys.argv[1] == "--apply"

PARSE_CODE = '''def main(llm_text: str, query_text: str) -> dict:
    import re
    q = re.sub(r"[\\s,，。.!！?？;；:：、]+", "", (query_text or "").lower())
    if any(x in q for x in ["算了", "不报了", "不用记录", "取消反馈", "结束反馈"]):
        return {"label": "ABANDON"}
    confirm = re.match(r"^(是的?|对的?|没错|正确|确认|可以|好的?|嗯+|没问题|信息准确|就这样)+", q)
    if confirm:
        rest = q[confirm.end():]
        if not rest:
            return {"label": "CONFIRM_NEW"}
        image_words = ["图片", "截图", "附件", "照片", "图"]
        attach_actions = ["上传", "附上", "带上", "保存", "记录", "提交"]
        change_markers = ["改成", "修改", "更正", "补充", "不是", "不对", "应该是", "调整为"]
        if any(x in rest for x in image_words) and any(x in rest for x in attach_actions) and not any(x in rest for x in change_markers):
            return {"label": "CONFIRM_NEW"}
    t = (llm_text or "").upper()
    for label in ["CONFIRM_NEW", "MODIFY_NEW", "MODIFY_EXISTING", "ABANDON", "BUG_NEW_TOPIC", "IRRELEVANT"]:
        if label in t:
            return {"label": label}
    return {"label": "IRRELEVANT"}'''

QUERY_VAR = {
    "variable": "query_text",
    "value_selector": ["6002", "query_text"],
}

N17_RULES = '''

【确认优先级补充规则】
- 用户先明确肯定，再说“记得把图片/截图/附件上传”等流程要求，仍输出 CONFIRM_NEW。
- 只有明确改变模块、操作描述、环境或类型时才输出 MODIFY_NEW。
'''

N5B_RULES = '''

【跨轮与附件规则】
- 上一轮结构化字段同样属于有效信息；四字段已完整时，不得因本轮附件处理要求重新判为 INSUFFICIENT。
- 当前 H5/客服窗口支持图片文件，严禁声称窗口无法接收文件或要求改走其他渠道。
- “上传图片/附上截图”是附件处理要求，不等于修改反馈四字段。
'''


def _append_prompt_rules(data: dict, prompt_id: str, rules: str) -> bool:
    for prompt in data.get("prompt_template") or []:
        if prompt.get("id") != prompt_id:
            continue
        text = prompt.get("text") or ""
        marker = rules.strip().splitlines()[0]
        if marker in text:
            return False
        prompt["text"] = text.rstrip() + rules
        return True
    return False


def mutate(graph: dict) -> tuple[dict, list[str]] | None:
    touched: list[str] = []
    for node in graph.get("nodes", []):
        node_id = str(node.get("id", ""))
        data = node.get("data") or {}
        changed = False

        if node_id == "6170":
            changed = _append_prompt_rules(data, "n17-sys", N17_RULES)

        if node_id == "6170-parse":
            if data.get("code") != PARSE_CODE:
                data["code"] = PARSE_CODE
                changed = True
            variables = data.get("variables") or []
            if not any(
                isinstance(item, dict) and item.get("variable") == "query_text"
                for item in variables
            ):
                data["variables"] = variables + [dict(QUERY_VAR)]
                changed = True

        if node_id == "6250b":
            changed = _append_prompt_rules(data, "n5b-sys", N5B_RULES) or changed

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

