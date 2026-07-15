#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根因 #7: A app L1(6101)加 out-of-domain 类(入口拦截非充电桩问题)。

问题: L1 无 out-of-domain 类,用户问非充电桩问题(闲聊/天气/写代码等)会被分到
      class_unclear(反复澄清)或 class_basic(走 L3 误处理/转 B 当 bug)。
修复:
  1. 6101 加 class_out_of_domain + instruction 规则 6
  2. 新增 6109-out(code 固定拒答话术,引用 6002.query_text)
  3. 6098(variable-aggregator)variables 加 ["6109-out","answer_text"]
  4. 加边 6101(class_out_of_domain)->6109-out->6098->6099(answer)
注意: 与充电/计费/设备/订单沾边的不判 out-of-domain(归 basic/unclear),避免过度拒答。

运行:
  ssh 124 'docker exec -i docker-api-1 python3 -'          < patch_7_a.py        # dry-run
  ssh 124 'docker exec -i docker-api-1 python3 - --apply'  < patch_7_a.py        # 部署
"""
import os, json, sys
import psycopg2, psycopg2.extras

AID = "33fde774-aeed-4026-a7f7-a0e339e1c030"  # A app charge_charging_A_kbqa
APPLY = (len(sys.argv) > 1 and sys.argv[1] == "--apply")

OUT_CODE = r'''def main(query_text: str) -> dict:
    q = (query_text or "").strip()
    snippet = q[:30] if q else "该问题"
    return {"answer_text": "您好,我是充电桩智能客服,仅能为您解答充电桩相关问题(如充电操作、计费收费、支付订单、设备故障、场地管理等)。您提到的\"" + snippet + "\"超出我的服务范围,暂时无法为您解答哦。请问有充电桩方面的问题需要咨询吗?"}'''

CLASS_OUT = {"id": "class_out_of_domain",
             "name": "非充电桩相关问题(与充电桩/充电服务平台明显完全无关,如闲聊/天气/新闻/写代码/其他行业咨询/情感问题等)"}

INSTR_OLD = "5. 只能选一个分类"
INSTR_NEW = INSTR_OLD + "\n6. 若用户问题与充电桩/充电服务平台明显完全无关(如闲聊/天气/新闻/写代码/其他行业咨询/情感问题) -> class_out_of_domain。注意:与充电/计费/设备/订单/场地等沾边的归 class_basic 或 class_unclear,严禁判 out-of-domain"


def patch_graph(g):
    nodes = g["nodes"]; edges = g["edges"]
    touched = []
    # 动态获取 code 节点出边 sourceHandle 惯例(从 6002 出边)+ 6098 入边 targetHandle
    code_sh = None
    for e in edges:
        if e.get("source") == "6002":
            code_sh = e.get("sourceHandle"); break
    th_6098 = "target"
    for e in edges:
        if e.get("source") == "6105" and e.get("target") == "6098":
            th_6098 = e.get("targetHandle", "target"); break
    if not APPLY:
        print("  [fmt] code sourceHandle=%r  6098 targetHandle=%r" % (code_sh, th_6098))

    for n in nodes:
        if n["id"] == "6101":
            d = n["data"]
            if not any(c.get("id") == "class_out_of_domain" for c in d.get("classes", [])):
                d["classes"].append(dict(CLASS_OUT)); touched.append("6101:+class_out_of_domain")
            instr = d.get("instruction", "")
            if INSTR_OLD in instr and "class_out_of_domain" not in instr:
                d["instruction"] = instr.replace(INSTR_OLD, INSTR_NEW, 1); touched.append("6101:instruction+rule6")
        if n["id"] == "6098":
            d = n["data"]
            vs = d.get("variables", [])
            if not any(v == ["6109-out", "answer_text"] for v in vs):
                vs.append(["6109-out", "answer_text"]); d["variables"] = vs; touched.append("6098:+var 6109-out")

    if not any(n["id"] == "6109-out" for n in nodes):
        new_node = {
            "id": "6109-out", "type": "custom",
            "position": {"x": 40, "y": 220}, "positionAbsolute": {"x": 40, "y": 220},
            "width": 242, "height": 88, "selected": False,
            "data": {"type": "code", "title": "L1 超出范围话术", "code_language": "python3",
                     "code": OUT_CODE,
                     "outputs": {"answer_text": {"children": None, "type": "string"}},
                     "variables": [{"variable": "query_text", "value_selector": ["6002", "query_text"]}]}}
        nodes.append(new_node); touched.append("add node 6109-out")

    e1 = {"id": "e-6101-ood-6109out", "source": "6101", "sourceHandle": "class_out_of_domain",
          "target": "6109-out", "targetHandle": "target", "type": "custom"}
    e2 = {"id": "e-6109out-6098", "source": "6109-out", "sourceHandle": code_sh,
          "target": "6098", "targetHandle": th_6098, "type": "custom"}
    if not any(e.get("id") == e1["id"] for e in edges):
        edges.append(e1); touched.append("edge 6101(ood)->6109-out")
    if not any(e.get("id") == e2["id"] for e in edges):
        edges.append(e2); touched.append("edge 6109-out->6098")
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
    cur.execute("SELECT id, version, graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC", (AID,))
    rows = cur.fetchall()
    print("AID=%s  published_rows=%d  APPLY=%s" % (AID, len(rows), APPLY))
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
        cur.execute("SELECT graph FROM workflows WHERE app_id=%s AND version!='draft' ORDER BY updated_at DESC LIMIT 1", (AID,))
        g = cur.fetchone()["graph"]
        if isinstance(g, str):
            g = json.loads(g)
        has_node = any(n["id"] == "6109-out" for n in g["nodes"])
        c6101 = next((n for n in g["nodes"] if n["id"] == "6101"), None)
        cls = [c["id"] for c in (c6101 or {}).get("data", {}).get("classes", [])]
        v6098 = next((n for n in g["nodes"] if n["id"] == "6098"), {}).get("data", {}).get("variables", [])
        e_ood = [e for e in g["edges"] if e.get("sourceHandle") == "class_out_of_domain"]
        print("  verify: node 6109-out=%s | 6101 classes=%s | 6098 has 6109-out=%s | ood edges=%d" % (
            has_node, cls, ["6109-out", "answer_text"] in v6098, len(e_ood)))
    else:
        print("\n[DRY-RUN] no writes. Re-run with --apply to deploy.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
