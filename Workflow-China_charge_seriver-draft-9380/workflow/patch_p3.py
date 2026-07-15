#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 批量修复: 模型lite + 6250b-if死case/default安全降级 + 6260a/6176a操作描述不拼mokuai + 6262字数。

基于业务:
  模型(#16): 判定/话术需稳定, 7节点(6250首轮转写充足度/6244确认话术/6262汇报/6173对比/6175修改汇报/6177否认转写/6239-trans修改窗转写)改qwen3.6-plus(对齐6170/6250b), provider=tongyi
  6250b-if(P3-LOW+#17): 删死fallback case(6250b-judge不返回FALLBACK); default走6250b-insuf(安全降级insufficient, 非sufficient误录)
  6260a/6176a(#11): 操作描述不拼mokuai(mokuai已有独立"模块/功能点"字段, 重复拼接冗余+污染查重)
  6262(隐患3): 50字->100字(汇报含record_id, 50字可能截断)

改draft+published。
运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_p3.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_p3.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

BID = "707dd6d2-059f-47c9-aaac-4638e74969c6"
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

MODEL_NODES = ["6250", "6244", "6262", "6173", "6175", "6177", "6239-trans"]
NEW_MODEL_NAME = "qwen3.6-plus"
NEW_MODEL_PROVIDER = "langgenius/tongyi/tongyi"

NEW_6260A_CODE = r'''def main(mokuai: str, caozuomiaoshu: str, huanjing: str, leixing: str) -> dict:
    import json
    fields = {}
    if mokuai:
        fields["模块/功能点"] = mokuai[:100]
    if caozuomiaoshu:
        fields["操作描述"] = caozuomiaoshu[:2000]
    if huanjing and huanjing in ("后台", "管家端", "用户端"):
        fields["环境"] = huanjing
    fields["类型"] = (leixing or "bug")[:10]
    fields["问题状态"] = "问题未查阅"
    fields["产品备注"] = (caozuomiaoshu or "")[:500]
    return {"body_json": json.dumps({"fields": fields}, ensure_ascii=False)}'''

NEW_6176A_CODE = r'''def main(record_id: str, feedback_zh: str, mokuai: str, huanjing: str, leixing: str) -> dict:
    import json
    fields = {}
    if mokuai:
        fields["模块/功能点"] = mokuai[:100]
    if feedback_zh:
        fields["操作描述"] = feedback_zh[:2000]
        fields["产品备注"] = feedback_zh[:500]
    if huanjing and huanjing in ("后台", "管家端", "用户端"):
        fields["环境"] = huanjing
    fields["类型"] = (leixing or "bug")[:10]
    return {"body_json": json.dumps({"record_id": record_id, "fields": fields}, ensure_ascii=False)}'''

P6262_OLD = "4. 50字以内"
P6262_NEW = "4. 100字以内"


def patch_graph(g):
    nodes = g["nodes"]; edges = g["edges"]
    touched = []
    for n in nodes:
        nid = n.get("id"); d = n.get("data", {})
        # 1. 模型
        if nid in MODEL_NODES:
            m = d.get("model", {})
            if m.get("name") != NEW_MODEL_NAME:
                m["name"] = NEW_MODEL_NAME
                m["provider"] = NEW_MODEL_PROVIDER
                m["mode"] = "chat"
                touched.append("%s:model->qwen3.6-plus" % nid)
        # 2. 6250b-if 删 fallback case
        if nid == "6250b-if":
            cases = d.get("cases", [])
            before = len(cases)
            cases[:] = [c for c in cases if c.get("case_id") != "fallback"]
            if len(cases) < before:
                touched.append("6250b-if:删fallback case")
        # 3. 6260a/6176a 操作描述不拼 mokuai
        if nid == "6260a":
            d["code"] = NEW_6260A_CODE
            touched.append("6260a:操作描述不拼mokuai")
        if nid == "6176a":
            d["code"] = NEW_6176A_CODE
            touched.append("6176a:操作描述不拼mokuai")
        # 4. 6262 50字->100字
        if nid == "6262":
            txt = d.get("prompt_template", [{}])[0].get("text", "")
            if P6262_OLD in txt:
                d["prompt_template"][0]["text"] = txt.replace(P6262_OLD, P6262_NEW, 1)
                touched.append("6262:50字->100字")
    # 2. 删边 6250b-if[fallback]->6250b-parse
    eb = len(edges)
    edges[:] = [e for e in edges if not (e.get("source") == "6250b-if" and e.get("sourceHandle") == "fallback")]
    if len(edges) < eb:
        touched.append("删边 6250b-if[fallback]->6250b-parse")
    # 2. default 边 6250b-parse -> 6250b-insuf (安全降级)
    for e in edges:
        if e.get("source") == "6250b-if" and e.get("sourceHandle") == "default" and e.get("target") == "6250b-parse":
            e["target"] = "6250b-insuf"
            touched.append("6250b-if[default]->6250b-insuf(安全降级)")
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
            if n.get("id") in MODEL_NODES:
                print("  %s model=%s" % (n["id"], n["data"].get("model", {}).get("name")))
            if n.get("id") == "6250b-if":
                cs = [c.get("case_id") for c in n["data"].get("cases", [])]
                print("  6250b-if cases=%s" % cs)
            if n.get("id") == "6260a":
                print("  6260a 操作描述拼mokuai=%s" % ("mokuai + " in n["data"].get("code", "")))
            if n.get("id") == "6262":
                print("  6262 100字=%s" % ("100字以内" in n["data"]["prompt_template"][0]["text"]))
        for e in g["edges"]:
            if e.get("source") == "6250b-if" and e.get("sourceHandle") == "default":
                print("  6250b-if[default]->%s" % e.get("target"))
    else:
        print("\n[DRY-RUN]")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
