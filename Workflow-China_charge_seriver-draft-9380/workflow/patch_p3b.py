#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3b: #4 N5首轮门槛 + 隐患1 设备编号追问 + #8 JSON正则容错。

基于业务:
  #4: 6250 prompt 加"4要素齐全即SUFFICIENT"原则(模块+操作+现象+终端), 用户ID/订单ID/桩编号是加分项非必填 -> 首轮不冗余引导
  隐患1: 6250 引导话术去掉固定追加设备编号(不每轮追问), 聚焦缺失的模块/操作/现象/终端
  #8: 6250-judge/6250b-parse JSON提取改 raw_decode(支持嵌套JSON, 原 re.search(r"\{[^{}]*\}") 不支持嵌套致字段空)

改draft+published。
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

# #4: 6250 prompt 加 SUFFICIENT 原则
P6250_OLD_SUF = '【信息充足度判定】满足任意1条即"信息不足":'
P6250_NEW_SUF = ('【判定原则】同时具备模块+操作路径+问题现象+终端环境4要素即判SUFFICIENT'
                 '(用户ID/订单ID/桩编号是加分项非必填, 无则不因此判INSUFFICIENT)。\n'
                 '【信息充足度判定】满足任意1条即"信息不足":')

# 隐患1: 6250 引导去设备编号固定追加
P6250_OLD_DEV = '针对缺失信息点精准提问(缺什么问什么),末尾追加"如果您有相关的用户ID、订单ID、充电桩编号,也可以一并提供,能帮助我们更快定位排查问题"。参考:模块不明问业务场景;现象笼统问操作步骤+异常现象;终端不明问web管理后台/管家端APP/用'
P6250_NEW_DEV = '针对缺失信息点精准提问(缺什么问什么),聚焦缺失的模块/操作/现象/终端,不追问用户ID/订单ID/桩编号(这些是加分项,用户主动提供才记录)。参考:模块不明问业务场景;现象笼统问操作步骤+异常现象;终端不明问web管理后台/管家端APP/用'

# #8: 6250-judge 新 code (raw_decode)
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
    obj = None
    try:
        idx = text.find("{")
        if idx >= 0:
            obj, _ = json.JSONDecoder().raw_decode(text[idx:])
    except Exception:
        obj = None
    if obj:
        mokuai=str(obj.get("mokuai","")).strip()[:50]
        caozuomiaoshu=str(obj.get("caozuomiaoshu","")).strip()[:500]
        huanjing=str(obj.get("huanjing","")).strip()[:20]
        leixing=str(obj.get("leixing","")).strip()[:20]
        search_keyword=str(obj.get("search_keyword","")).strip()[:20]
    return {"label": label, "mokuai": mokuai, "caozuomiaoshu": caozuomiaoshu, "huanjing": huanjing, "leixing": leixing, "search_keyword": search_keyword}'''

# #8: 6250b-parse 新 code (raw_decode)
NEW_6250B_PARSE_CODE = r'''def main(llm_text: str, label: str) -> dict:
    import json, re
    if label == "FALLBACK":
        return {"mokuai":"待人工核实","caozuomiaoshu":"用户多次补充后信息仍不完整,需人工跟进核实具体问题","huanjing":"待确认","leixing":"bug","search_keyword":""}
    text = llm_text or ""
    obj = None
    try:
        idx = text.find("{")
        if idx >= 0:
            obj, _ = json.JSONDecoder().raw_decode(text[idx:])
    except Exception:
        obj = None
    if not obj:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":"","search_keyword":""}
    return {
        "mokuai": str(obj.get("mokuai","")).strip()[:50],
        "caozuomiaoshu": str(obj.get("caozuomiaoshu","")).strip()[:500],
        "huanjing": str(obj.get("huanjing","")).strip()[:20],
        "leixing": str(obj.get("leixing","")).strip()[:20],
        "search_keyword": str(obj.get("search_keyword","")).strip()[:20]
    }'''


def patch_graph(g):
    touched = []
    for n in g.get("nodes", []):
        nid = n.get("id"); d = n.get("data", {})
        if nid == "6250":
            txt = d.get("prompt_template", [{}])[0].get("text", "")
            if P6250_OLD_SUF in txt and "判定原则" not in txt:
                txt = txt.replace(P6250_OLD_SUF, P6250_NEW_SUF, 1)
                touched.append("6250:+SUFFICIENT原则(#4)")
            if P6250_OLD_DEV in txt:
                txt = txt.replace(P6250_OLD_DEV, P6250_NEW_DEV, 1)
                touched.append("6250:去设备编号追问(隐患1)")
            d["prompt_template"][0]["text"] = txt
        if nid == "6250-judge":
            d["code"] = NEW_6250_JUDGE_CODE
            touched.append("6250-judge:raw_decode(#8)")
        if nid == "6250b-parse":
            d["code"] = NEW_6250B_PARSE_CODE
            touched.append("6250b-parse:raw_decode(#8)")
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
            if n.get("id") == "6250":
                txt = n["data"]["prompt_template"][0]["text"]
                print("  6250 has 判定原则:", "判定原则" in txt)
                print("  6250 no 设备编号追问:", "末尾追加" not in txt)
            if n.get("id") == "6250-judge":
                print("  6250-judge raw_decode:", "raw_decode" in n["data"].get("code", ""))
            if n.get("id") == "6250b-parse":
                print("  6250b-parse raw_decode:", "raw_decode" in n["data"].get("code", ""))
    else:
        print("\n[DRY-RUN]")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
