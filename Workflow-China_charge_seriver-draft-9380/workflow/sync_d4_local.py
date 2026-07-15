#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步本地 charge_charging_B.yml 的 6240-parse + 6242 到已部署的 #3 修复版。"""
from ruamel.yaml import YAML

PATH = "/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_B.yml"

NEW_6240_PARSE = r'''def main(http_body: str) -> dict:
    import json
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

NEW_6242 = r'''def main(row_summary: str) -> dict:
    s = (row_summary or "").strip()
    if not s:
        s = "该记录内容"
    return {"answer_text": "您好,这个问题我们之前已经记录在跟进中了:\n" + s + "\n\n请问您这次反馈的是同一个问题吗?"}'''

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(PATH, encoding="utf-8") as f:
    data = yaml.load(f)

cnt = 0
for n in data["workflow"]["graph"]["nodes"]:
    nid = n.get("id")
    if nid == "6240-parse":
        n["data"]["code"] = NEW_6240_PARSE
        cnt += 1
    elif nid == "6242":
        n["data"]["code"] = NEW_6242
        cnt += 1

with open(PATH, "w", encoding="utf-8") as f:
    yaml.dump(data, f)
print("synced %d nodes in charge_charging_B.yml" % cnt)
