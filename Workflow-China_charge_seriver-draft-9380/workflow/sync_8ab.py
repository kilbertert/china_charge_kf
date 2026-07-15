#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 #8-a/#8-b 改动到本地 charge_charging_B.yml(与 124 graph 对齐)。
复用 patch_8ab.py 的常量,用 ruamel 改 workflow.graph 三节点。"""
from ruamel.yaml import YAML

YML = "charge_charging_B.yml"

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
    if module and op_desc.startswith(module):
        op_desc = op_desc[len(module):].lstrip()
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

NEW_6175_PARSE_CODE = r'''def main(llm_text: str) -> dict:
    import re
    t = llm_text or ""
    m1 = re.search(r"【修改后内容】(.+?)(【汇报话术】|$)", t, re.S)
    m2 = re.search(r"【汇报话术】(.+)", t, re.S)
    content = m1.group(1).strip() if m1 else t
    huibao = m2.group(1).strip() if m2 else t
    content = re.sub(r"^(所属模块|模块|功能点)[:：][^,，\n]{1,30}[,，]\s*", "", content).strip()
    return {"content": content, "huibao": huibao}'''

P6175_OLD = "1. 整合出修改后的操作描述(纯内容,无问候,将写入操作描述字段)"
P6175_NEW = "1. 整合出修改后的操作描述(纯问题描述:直接写操作终端+操作路径+问题现象+业务影响,严禁带【所属模块:】【模块:】等任何字段标签前缀,严禁重复模块名,无问候语,将写入操作描述字段)"


def main():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(YML, "r", encoding="utf-8") as f:
        doc = yaml.load(f)
    graph = doc["workflow"]["graph"]
    touched = []
    for n in graph["nodes"]:
        nid = n.get("id")
        d = n.get("data")
        if nid == "6240-parse":
            d["code"] = NEW_6240_PARSE_CODE
            touched.append("6240-parse:code")
        elif nid == "6175-parse":
            d["code"] = NEW_6175_PARSE_CODE
            touched.append("6175-parse:code")
        elif nid == "6175":
            pts = d.get("prompt_template", [])
            if pts and isinstance(pts[0].get("text"), str):
                txt = pts[0]["text"]
                if P6175_OLD in txt:
                    pts[0]["text"] = txt.replace(P6175_OLD, P6175_NEW, 1)
                    touched.append("6175:prompt")
                elif "严禁带" in txt:
                    touched.append("6175:prompt already done")
    with open(YML, "w", encoding="utf-8") as f:
        yaml.dump(doc, f)
    print("synced:", touched)


main()
