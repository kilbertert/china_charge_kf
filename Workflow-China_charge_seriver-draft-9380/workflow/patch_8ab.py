#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因 #8-a/#8-b: 修 D4 命中汇报与 modify 路径的模块名重复。

#8-a (6240-parse): 查表回的 op_desc 存储格式 = "{module} {caozuomiaoshu}"
      (6260a/6176a 拼接), row_summary 里"所属模块"和"问题描述"重复模块名。
      修复: 剥离 op_desc 开头的 module 前缀; 防御性剥离 LLM 误加的
      "所属模块:XXX,"前缀(历史脏数据)。

#8-b (6175-parse + 6175 prompt): modify 路径 6175 LLM 把"修改后内容"写成
      "所属模块:XX,用户反馈...", 经 6175-parse -> cv_feedback_zh -> 6176a
      "操作描述 = mokuai + feedback_zh" 导致模块名三重重复。
      修复: 6175 prompt 强化"纯描述,禁字段标签/模块名";
            6175-parse 防御性剥离 content 的"所属模块:"前缀。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_8ab.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_8ab.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 6240-parse: 剥离 op_desc 的 module 前缀 + "所属模块:"前缀
NEW_6240_PARSE_CODE = r'''def main(http_body: str) -> dict:
    import json, re
    try:
        data = json.loads(http_body or "{}")
    except Exception:
        return {"hit_record_id": "", "row_summary": ""}
    hits = data.get("hits") or []
    if not hits:
        return {"hit_record_id": "", "row_summary": ""}
    h = hits[0]
    rid = h.get("record_id", "")
    module = (h.get("module") or "").strip()
    op_desc = (h.get("op_desc") or h.get("summary") or "").strip()
    # 剥离存储时拼接的 module 前缀(op_desc 存储 = "{module} {caozuomiaoshu}")
    if module and op_desc.startswith(module):
        op_desc = op_desc[len(module):].lstrip()
    # 防御:剥离 LLM 误加的"所属模块:XXX,"前缀(历史脏数据)
    op_desc = re.sub(r"^(所属模块|模块|功能点)[:：][^,，\n]{1,30}[,，]\s*", "", op_desc).strip()
    dev_status = (h.get("dev_status") or "").strip()
    reply = (h.get("reply") or "").strip()
    result = (h.get("result") or "").strip()
    parts = []
    if module:
        parts.append("所属模块:" + module)
    if op_desc:
        parts.append("问题描述:" + op_desc)
    if dev_status:
        parts.append("当前状态:" + dev_status)
    if reply:
        parts.append("产品回复:" + reply)
    if result:
        parts.append("完成结果:" + result)
    row_summary = "\n".join(parts) if parts else op_desc[:500]
    return {"hit_record_id": rid, "row_summary": row_summary}'''

# 6175-parse: content 剥离"所属模块:"前缀(防御 LLM 误加)
NEW_6175_PARSE_CODE = r'''def main(llm_text: str) -> dict:
    import re
    t = llm_text or ""
    m1 = re.search(r"【修改后内容】(.+?)(【汇报话术】|$)", t, re.S)
    m2 = re.search(r"【汇报话术】(.+)", t, re.S)
    content = m1.group(1).strip() if m1 else t
    huibao = m2.group(1).strip() if m2 else t
    # 防御:剥离 LLM 误加的"所属模块:XXX,"前缀,只留纯操作描述
    content = re.sub(r"^(所属模块|模块|功能点)[:：][^,，\n]{1,30}[,，]\s*", "", content).strip()
    return {"content": content, "huibao": huibao}'''

# 6175 prompt: 强化"修改后内容"为纯描述,禁字段标签/模块名
P6175_OLD = "1. 整合出修改后的操作描述(纯内容,无问候,将写入操作描述字段)"
P6175_NEW = "1. 整合出修改后的操作描述(纯问题描述:直接写操作终端+操作路径+问题现象+业务影响,严禁带【所属模块:】【模块:】等任何字段标签前缀,严禁重复模块名,无问候语,将写入操作描述字段)"


def patch_graph(g):
    """对单个 graph 做 3 节点改动, 返回 touched 列表。"""
    nodes = g.get("nodes", [])
    touched = []
    for n in nodes:
        nid = n.get("id")
        d = n.get("data", {})
        if nid == "6240-parse":
            d["code"] = NEW_6240_PARSE_CODE
            touched.append("6240-parse:code(strip module prefix + 所属模块: prefix)")
        elif nid == "6175-parse":
            d["code"] = NEW_6175_PARSE_CODE
            touched.append("6175-parse:code(strip 所属模块: prefix from content)")
        elif nid == "6175":
            pts = d.get("prompt_template", [])
            if pts and isinstance(pts[0].get("text"), str):
                txt = pts[0]["text"]
                if P6175_OLD in txt:
                    pts[0]["text"] = txt.replace(P6175_OLD, P6175_NEW, 1)
                    touched.append("6175:prompt(strengthen 纯描述约束)")
                elif "严禁带" in txt:
                    touched.append("6175:prompt already strengthened")
                else:
                    touched.append("6175:prompt OLD substring NOT FOUND (skip)")
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
    cur.execute("SELECT id, version, graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC", (BID,))
    rows = cur.fetchall()
    print("BID=%s  published_rows=%d  APPLY=%s" % (BID, len(rows), APPLY))
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
        print("  %s version=%s -> %s" % ("patched" if APPLY else "would-patch", r["version"], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC LIMIT 1", (BID,))
        g = cur.fetchone()["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        for n in g.get("nodes", []):
            nid = n.get("id")
            d = n.get("data", {})
            if nid == "6240-parse":
                c = d.get("code", "")
                print("  verify 6240-parse: strip module prefix =", "op_desc.startswith(module)" in c, "| strip 所属模块: =", "所属模块|模块|功能点" in c)
            elif nid == "6175-parse":
                c = d.get("code", "")
                print("  verify 6175-parse: strip 所属模块: from content =", "所属模块|模块|功能点" in c)
            elif nid == "6175":
                txt = d.get("prompt_template", [{}])[0].get("text", "")
                print("  verify 6175 prompt: 严禁带 =", "严禁带" in txt)
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
