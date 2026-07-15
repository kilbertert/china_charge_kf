#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 fix3: 修R2过早ESCALATE + R3空回复(基于业务:6170判关系不判count,ESCALATE由6250b-judge确定性触发)。

根因(第三轮V-esc-reg):
  ESCALATE有两条路径:
    A. 6170判ESCALATE->6171[escalate]->6250b-escalate-abort (LLM判count不可靠,R2 count=1就判ESCALATE过早)
    B. 6250b-judge count>=3->6250b-if[escalate]->6250b-escalate-abort (code确定性,正确)
  6170职责是判关系(语义),不该判count(确定性)。路径A多余且不可靠。
  R3空回复:R2过早ESCALATE(切KB SWICH_TO_KB_DONE)+IDLE, R3重新进6250但状态混乱->空。
  V-esc旁路:6170模糊补充误判IRRELEVANT->6162->KB_REENTRY空回复。

修复(基于业务):
  1. 6170移除ESCALATE标签+cv_clarify_count注入(不判count), 加"模糊补充->MODIFY_NEW"强调(防旁路)
  2. 6170-parse移除ESCALATE label(6170不输出ESCALATE)
  3. 6171移除escalate case + 删边6171[escalate]->6250b-escalate-abort
  4. 6250b-judge/6250b-if[escalate]/6250b-escalate-abort保留(路径B, ESCALATE由6250b-judge count>=3确定性触发)

效果: 用户模糊补充->6170判MODIFY_NEW->6250b->6250b-judge count递增
      count<3 INSUFFICIENT引导; count>=3 ESCALATE转人工(确定性,不靠LLM)

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_p2_fix3.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_p2_fix3.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 6170-parse 回原(移除ESCALATE)
NEW_6170_PARSE_CODE = r'''def main(llm_text: str) -> dict:
    import re
    t = (llm_text or "").upper()
    for label in ["CONFIRM_NEW", "MODIFY_NEW", "MODIFY_EXISTING", "ABANDON", "IRRELEVANT"]:
        if label in t:
            return {"label": label}
    return {"label": "IRRELEVANT"}'''

# 6170 prompt 子串 replace
P6170_REPLACES = [
    # 移除 cv_clarify_count 注入
    ("【用户新消息】: {{#6002.query_text#}}\n【已引导补充次数】: {{#conversation.cv_clarify_count#}}\n",
     "【用户新消息】: {{#6002.query_text#}}\n"),
    # 移除 ESCALATE 标签
    ("- ABANDON          : 用户要结束/放弃本次反馈,不是开新话题(算了/不报了/没事/不用了/结束吧)\n- ESCALATE         : 已引导补充次数>=3 且用户仍模糊/说不清楚/无法提供有效信息(转人工)\n- IRRELEVANT        : 开新话题/与待确认事项无关",
     "- ABANDON          : 用户要结束/放弃本次反馈,不是开新话题(算了/不报了/没事/不用了/结束吧)\n- IRRELEVANT        : 开新话题/与待确认事项无关(如查计费规则/怎么操作等非反馈类)"),
    # MODIFY_NEW 强调(模糊补充也算)
    ("- MODIFY_NEW        : 用户补充或要求修改新反馈内容\n",
     "- MODIFY_NEW        : 用户补充或要求修改新反馈内容(包括模糊/说不清楚的补充,只要与当前反馈相关都算补充)\n"),
    # 判定要点2 强调
    ("2. 用户补充反馈内容或要求改某字段 -> MODIFY_NEW\n",
     "2. 用户补充反馈内容/要求改字段/模糊补充(如\"不好用/说不清楚/反正有问题\") -> MODIFY_NEW\n"),
]


def patch_graph(g):
    touched = []
    for n in g.get("nodes", []):
        nid = n.get("id"); d = n.get("data", {})
        if nid == "6170":
            txt = d.get("prompt_template", [{}])[0].get("text", "")
            for old, new in P6170_REPLACES:
                if old in txt:
                    txt = txt.replace(old, new, 1)
                    touched.append("6170:replace %s" % old[:30])
            d["prompt_template"][0]["text"] = txt
        if nid == "6170-parse":
            d["code"] = NEW_6170_PARSE_CODE
            touched.append("6170-parse:移除ESCALATE label")
        if nid == "6171":
            cases = d.get("cases", [])
            before = len(cases)
            cases[:] = [c for c in cases if c.get("case_id") != "escalate"]
            if len(cases) < before:
                touched.append("6171:移除escalate case")
    # 删边 6171[escalate]->6250b-escalate-abort
    eb = len(g["edges"])
    g["edges"][:] = [e for e in g["edges"] if not (e.get("source") == "6171" and e.get("sourceHandle") == "escalate")]
    if len(g["edges"]) < eb:
        touched.append("删边 6171[escalate]->6250b-escalate-abort")
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
    cur.execute("SELECT id, version, graph FROM workflows WHERE app_id=%s ORDER BY updated_at DESC", (BID,))
    rows = cur.fetchall()
    print("rows=%d APPLY=%s" % (len(rows), APPLY))
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
        print("  %s ver=%s -> %s" % ("patched" if APPLY else "would-patch", str(r["version"])[:20], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] %d rows" % changed)
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s ORDER BY updated_at DESC LIMIT 1", (BID,))
        g = json.loads(cur.fetchone()["graph"])
        for n in g["nodes"]:
            if n.get("id") == "6170":
                txt = n["data"]["prompt_template"][0]["text"]
                print("  6170 has ESCALATE:", "ESCALATE" in txt, "| has cv_clarify_count:", "cv_clarify_count" in txt)
                print("  6170 has MODIFY_NEW强调:", "模糊/说不清楚" in txt)
            if n.get("id") == "6170-parse":
                print("  6170-parse has ESCALATE:", "ESCALATE" in n["data"].get("code", ""))
            if n.get("id") == "6171":
                cs = [c.get("case_id") for c in n["data"].get("cases", [])]
                print("  6171 cases:", cs)
        print("  6171[escalate]边存在:", any(e.get("source") == "6171" and e.get("sourceHandle") == "escalate" for e in g["edges"]))
        print("  6250b-if[escalate]->abort存在:", any(e.get("source") == "6250b-if" and e.get("sourceHandle") == "escalate" for e in g["edges"]))
    else:
        print("\n[DRY-RUN]")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
