#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 彻底修复: memory缺失 + huanjing未写飞书 + search_keyword多轮退化。

根因(彻查):
  P0-1 memory: #1 patch_memory 只改 published(version!='draft')不改 draft;
       7/11 UI 发布新版本从 draft 复制 -> 新 published 丢 memory(6170 系列全 False)。
       修复必须改 draft + published。
  P0-2 huanjing: 6260a/6176a vars 漏 huanjing(cv_huanjing 有值却丢弃), 飞书"环境"列空。
  P0-3 search_keyword: 6250b 不输出/不提取;6243-pre/6243b 不设 cv_search_keyword;
       6240build 引用 6250-judge.search_keyword(节点输出)非 cv -> 迭代轮 6250-judge 没执行,
       search_keyword 空, 退化 mokuai 宽泛匹配误命中。

业务:
  memory = LLM 判相关性/转写/话术需对话历史(基础设施)
  huanjing = 飞书记录需终端环境维度供研发排查
  search_keyword = 查重需每轮最新核心词, 跨轮维护在 cv(非节点输出)

改 draft + 所有 published 的 graph 列 + conversation_variables 列。
运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_p0.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_p0.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")
MEMORY = {"window": {"enabled": True, "size": 10}}
MEM_NODES = ["6170", "6170b", "6170c", "6170d", "6173", "6175", "6177", "6239-llm", "6239-trans"]

# P0-3: 6250b prompt JSON schema 加 search_keyword
P6250B_OLD = '"leixing":"bug/优化(无法判定填待确认)"}'
P6250B_NEW = ('"leixing":"bug/优化(无法判定填待确认)",'
              '"search_keyword":"2-6字核心问题词,用于查重搜已有记录'
              '(如扫码/离线/支付失败/订单结束),取最核心名词或动宾,'
              '不同客户对同类问题应输出相同词"}')

# P0-3: 6250b-parse 新 code (提取 search_keyword)
NEW_6250B_PARSE_CODE = r'''def main(llm_text: str, label: str) -> dict:
    import json, re
    if label == "FALLBACK":
        return {"mokuai":"待人工核实","caozuomiaoshu":"用户多次补充后信息仍不完整,需人工跟进核实具体问题","huanjing":"待确认","leixing":"bug","search_keyword":""}
    text = llm_text or ""
    m = re.search(r"\{[^{}]*\}", text)
    if not m:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":"","search_keyword":""}
    try:
        obj = json.loads(m.group(0))
        return {
            "mokuai": str(obj.get("mokuai","")).strip()[:50],
            "caozuomiaoshu": str(obj.get("caozuomiaoshu","")).strip()[:500],
            "huanjing": str(obj.get("huanjing","")).strip()[:20],
            "leixing": str(obj.get("leixing","")).strip()[:20],
            "search_keyword": str(obj.get("search_keyword","")).strip()[:20]
        }
    except Exception:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":"","search_keyword":""}'''

NEW_6250B_PARSE_OUTPUTS = {
    "mokuai": {"children": None, "type": "string"},
    "caozuomiaoshu": {"children": None, "type": "string"},
    "huanjing": {"children": None, "type": "string"},
    "leixing": {"children": None, "type": "string"},
    "search_keyword": {"children": None, "type": "string"},
}

# P0-2: 6260a 新 code (加 huanjing 写"环境", 仅有效选项)
NEW_6260A_CODE = r'''def main(mokuai: str, caozuomiaoshu: str, huanjing: str, leixing: str) -> dict:
    import json
    fields = {}
    if mokuai:
        fields["模块/功能点"] = mokuai[:100]
    if caozuomiaoshu:
        fields["操作描述"] = ((mokuai + " ") if mokuai else "") + caozuomiaoshu[:2000]
    if huanjing and huanjing in ("后台", "管家端", "用户端"):
        fields["环境"] = huanjing
    fields["类型"] = (leixing or "bug")[:10]
    fields["问题状态"] = "问题未查阅"
    fields["产品备注"] = (caozuomiaoshu or "")[:500]
    return {"body_json": json.dumps({"fields": fields}, ensure_ascii=False)}'''

# P0-2: 6176a 新 code (加 huanjing 写"环境")
NEW_6176A_CODE = r'''def main(record_id: str, feedback_zh: str, mokuai: str, huanjing: str, leixing: str) -> dict:
    import json
    fields = {}
    if mokuai:
        fields["模块/功能点"] = mokuai[:100]
    if feedback_zh:
        fields["操作描述"] = ((mokuai + " ") if mokuai else "") + feedback_zh[:2000]
        fields["产品备注"] = feedback_zh[:500]
    if huanjing and huanjing in ("后台", "管家端", "用户端"):
        fields["环境"] = huanjing
    fields["类型"] = (leixing or "bug")[:10]
    return {"body_json": json.dumps({"record_id": record_id, "fields": fields}, ensure_ascii=False)}'''

# P0-3: cv_search_keyword 声明 (加到 conversation_variables dict)
CV_SEARCH = {
    "value_type": "string", "value": "",
    "id": "a1b2c3d4-0010-4000-8000-000000000010",
    "name": "cv_search_keyword",
    "description": "查重核心词(跨轮保留供6240build查表, N5/N5b提取)",
    "selector": ["conversation", "cv_search_keyword"],
}


def add_assigner_item(items, variable_selector, value_selector):
    """assigner items 加一项 (variable_selector=[conversation,cv_xxx], value=[node,out])"""
    if not any(it.get("variable_selector") == variable_selector for it in items):
        items.append({
            "input_type": "variable",
            "operation": "over-write",
            "value": value_selector,
            "variable_selector": variable_selector,
        })
        return True
    return False


def patch_graph(g):
    touched = []
    for n in g.get("nodes", []):
        nid = n.get("id")
        d = n.get("data", {})
        # P0-1 memory
        if nid in MEM_NODES:
            if not d.get("memory"):
                d["memory"] = json.loads(json.dumps(MEMORY))
                touched.append("%s:+memory" % nid)
        # P0-3 6250b prompt JSON schema 加 search_keyword
        if nid == "6250b":
            pts = d.get("prompt_template", [])
            if pts and isinstance(pts[0].get("text"), str) and P6250B_OLD in pts[0]["text"]:
                pts[0]["text"] = pts[0]["text"].replace(P6250B_OLD, P6250B_NEW, 1)
                touched.append("6250b:prompt+search_keyword")
        # P0-3 6250b-parse code + outputs 加 search_keyword
        if nid == "6250b-parse":
            d["code"] = NEW_6250B_PARSE_CODE
            d["outputs"] = json.loads(json.dumps(NEW_6250B_PARSE_OUTPUTS))
            touched.append("6250b-parse:code+outputs+search_keyword")
        # P0-3 6240build vars: search_keyword <- cv_search_keyword (code 不变, kw=sk or mokuai)
        if nid == "6240build":
            vs = d.get("variables", [])
            existing = next((v for v in vs if v.get("variable") == "search_keyword"), None)
            if existing:
                if existing.get("value_selector") != ["conversation", "cv_search_keyword"]:
                    existing["value_selector"] = ["conversation", "cv_search_keyword"]
                    touched.append("6240build:var search_keyword<-cv_search_keyword")
            else:
                vs.append({"variable": "search_keyword", "value_selector": ["conversation", "cv_search_keyword"]})
                d["variables"] = vs
                touched.append("6240build:+var search_keyword<-cv_search_keyword")
        # P0-2 6260a code + huanjing var
        if nid == "6260a":
            d["code"] = NEW_6260A_CODE
            vs = d.get("variables", [])
            if not any(v.get("variable") == "huanjing" for v in vs):
                vs.append({"variable": "huanjing", "value_selector": ["conversation", "cv_huanjing"]})
                d["variables"] = vs
            touched.append("6260a:code+huanjing var")
        # P0-2 6176a code + huanjing var
        if nid == "6176a":
            d["code"] = NEW_6176A_CODE
            vs = d.get("variables", [])
            if not any(v.get("variable") == "huanjing" for v in vs):
                vs.append({"variable": "huanjing", "value_selector": ["conversation", "cv_huanjing"]})
                d["variables"] = vs
            touched.append("6176a:code+huanjing var")
        # P0-3 6243-pre / 6243b 加 cv_search_keyword item
        if nid in ("6243-pre", "6243b"):
            src = ["6250-judge", "search_keyword"] if nid == "6243-pre" else ["6250b-parse", "search_keyword"]
            items = d.get("items", [])
            if add_assigner_item(items, ["conversation", "cv_search_keyword"], src):
                d["items"] = items
                touched.append("%s:+cv_search_keyword item" % nid)
    return touched


def patch_conv_vars(cv_obj):
    """conversation_variables dict 加 cv_search_keyword"""
    touched = []
    if isinstance(cv_obj, dict) and "cv_search_keyword" not in cv_obj:
        cv_obj["cv_search_keyword"] = json.loads(json.dumps(CV_SEARCH))
        touched.append("conv_vars:+cv_search_keyword")
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
    # 含 draft + published (根因: draft 不改则 UI 发布丢)
    cur.execute("SELECT id, version, graph, conversation_variables FROM workflows WHERE app_id=%s ORDER BY updated_at DESC", (BID,))
    rows = cur.fetchall()
    print("BID=%s  rows=%d (含draft)  APPLY=%s" % (BID, len(rows), APPLY))
    changed = 0
    for r in rows:
        g = r["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        cv = r["conversation_variables"]
        cv = json.loads(cv) if isinstance(cv, str) else (cv or {})
        tg = patch_graph(g)
        tc = patch_conv_vars(cv)
        touched = tg + tc
        if not touched:
            continue
        if APPLY:
            cur.execute(
                "UPDATE workflows SET graph=%s, conversation_variables=%s WHERE id=%s",
                (json.dumps(g, ensure_ascii=False), json.dumps(cv, ensure_ascii=False), r["id"]),
            )
            changed += cur.rowcount
        print("  %s ver=%s -> %s" % ("patched" if APPLY else "would-patch", str(r["version"])[:20], touched))
    if APPLY:
        conn.commit()
        print("\n[APPLIED] updated %d rows" % changed)
        # verify 最新版本(含 draft)
        cur.execute("SELECT version, graph, conversation_variables FROM workflows WHERE app_id=%s ORDER BY updated_at DESC LIMIT 1", (BID,))
        r = cur.fetchone()
        g = json.loads(r["graph"]) if isinstance(r["graph"], str) else r["graph"]
        cv = json.loads(r["conversation_variables"]) if isinstance(r["conversation_variables"], str) else r["conversation_variables"]
        print("  verify latest ver=%s" % str(r["version"])[:20])
        for n in g["nodes"]:
            if n["id"] in MEM_NODES:
                print("    %s memory=%s" % (n["id"], bool(n["data"].get("memory"))))
        print("    cv_search_keyword in conv_vars:", "cv_search_keyword" in cv)
        for nid in ("6260a", "6176a", "6240build", "6250b-parse"):
            for n in g["nodes"]:
                if n["id"] == nid:
                    if nid in ("6260a", "6176a"):
                        print("    %s huanjing var=%s | code has 环境=%s" % (
                            nid, any(v.get("variable") == "huanjing" for v in n["data"].get("variables", [])),
                            "环境" in n["data"].get("code", "")))
                    elif nid == "6240build":
                        print("    %s search_keyword<-cv=%s" % (nid, ["conversation", "cv_search_keyword"] in
                            [v.get("value_selector") for v in n["data"].get("variables", [])]))
                    elif nid == "6250b-parse":
                        print("    %s outputs has search_keyword=%s" % (nid, "search_keyword" in (n["data"].get("outputs") or {})))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
