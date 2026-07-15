#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因6: 修 D2 查表 keyword 不匹配 (charge B 的 6250 prompt + 6250-judge + 6240build)。

问题: 6240build 用 cv_mokuai(模块名,如"充电桩设备状态管理") 在"操作描述"contains,
      但模块名跨报告不一致(同问题不同模块名) -> 几乎0命中 -> D4不触发。
修复: 6250 LLM 额外提取 search_keyword(2-6字核心问题词,如扫码/离线/支付失败),
      6240build 优先用 search_keyword(空则回退 cv_mokuai)。主路径(6250)生效,
      6250b/6177 路径 search_keyword 为空自动回退 mokuai(旧行为)。
保留: 不碰 model(保留用户#2的qwen-plus切换), 只改 prompt/code/outputs/variables。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_search_keyword.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_search_keyword.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# 6250 prompt: 在 JSON schema 末尾加 search_keyword 字段
PROMPT_OLD = '"leixing":"bug/优化(无法判定填待确认)"}'
PROMPT_NEW = '"leixing":"bug/优化(无法判定填待确认)","search_keyword":"2-6字核心问题词,用于查重搜已有记录(如扫码/离线/支付失败/订单结束),取最核心名词或动宾,不同客户对同类问题应输出相同词"}'

# 6250-judge: 新 code (含#4的NOT SUFFICIENT修复 + 提取 search_keyword)
NEW_6250_JUDGE_CODE = r'''def main(llm_text: str) -> dict:
    import json, re
    text = llm_text or ""
    t = text.upper()
    if "INSUFFICIENT" in t or "NOT SUFFICIENT" in t:
        label = "INSUFFICIENT"
    elif "SUFFICIENT" in t:
        label = "SUFFICIENT"
    else:
        label = "INSUFFICIENT"
    mokuai=caozuomiaoshu=huanjing=leixing=search_keyword=""
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            mokuai=str(obj.get("mokuai","")).strip()[:50]
            caozuomiaoshu=str(obj.get("caozuomiaoshu","")).strip()[:500]
            huanjing=str(obj.get("huanjing","")).strip()[:20]
            leixing=str(obj.get("leixing","")).strip()[:20]
            search_keyword=str(obj.get("search_keyword","")).strip()[:20]
        except Exception:
            pass
    return {"label": label, "mokuai": mokuai, "caozuomiaoshu": caozuomiaoshu, "huanjing": huanjing, "leixing": leixing, "search_keyword": search_keyword}'''

# 6250-judge outputs: 加 search_keyword
NEW_6250_JUDGE_OUTPUTS = {
    "label": {"children": None, "type": "string"},
    "mokuai": {"children": None, "type": "string"},
    "caozuomiaoshu": {"children": None, "type": "string"},
    "huanjing": {"children": None, "type": "string"},
    "leixing": {"children": None, "type": "string"},
    "search_keyword": {"children": None, "type": "string"},
}

# 6240build: 优先 search_keyword, 空则回退 mokuai
NEW_6240BUILD_CODE = r'''def main(mokuai: str, search_keyword: str) -> dict:
    import json
    kw = (search_keyword or "").strip() or (mokuai or "").strip()
    return {"body_json": json.dumps({"keyword": kw, "limit": 5}, ensure_ascii=False)}'''


def patch_graph(g):
    """对单个 graph 做 3 节点改动, 返回 (touched, details)。"""
    nodes = g.get("nodes", [])
    touched = []
    for n in nodes:
        nid = n.get("id")
        d = n.get("data", {})
        if nid == "6250":
            # prompt_template[0].text 替换
            pts = d.get("prompt_template", [])
            if pts and isinstance(pts[0].get("text"), str):
                txt = pts[0]["text"]
                if PROMPT_OLD in txt:
                    pts[0]["text"] = txt.replace(PROMPT_OLD, PROMPT_NEW, 1)
                    touched.append("6250:prompt+search_keyword")
                elif "search_keyword" in txt:
                    touched.append("6250:prompt already has search_keyword")
                else:
                    touched.append("6250:prompt OLD substring NOT FOUND (skip)")
        elif nid == "6250-judge":
            d["code"] = NEW_6250_JUDGE_CODE
            d["outputs"] = NEW_6250_JUDGE_OUTPUTS
            touched.append("6250-judge:code+outputs+search_keyword")
        elif nid == "6240build":
            d["code"] = NEW_6240BUILD_CODE
            vars_ = d.get("variables", [])
            if not any(v.get("variable") == "search_keyword" for v in vars_):
                vars_.append({"variable": "search_keyword", "value_selector": ["6250-judge", "search_keyword"]})
                d["variables"] = vars_
            touched.append("6240build:code+var(search_keyword<-6250-judge)")
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
            if nid == "6250":
                txt = d.get("prompt_template", [{}])[0].get("text", "")
                print("  verify 6250 prompt has search_keyword:", "search_keyword" in txt)
            elif nid == "6250-judge":
                print("  verify 6250-judge code has search_keyword:", "search_keyword" in d.get("code", ""))
            elif nid == "6240build":
                vs = [v.get("variable") for v in d.get("variables", [])]
                print("  verify 6240build vars:", vs, "| code has fallback:", "search_keyword" in d.get("code", ""))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


main()
