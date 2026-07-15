#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步本地 charge_charging_B.yml 的 6250/6250-judge/6240build 到已部署的 #6 修复版。"""
from ruamel.yaml import YAML

PATH = "/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_B.yml"

PROMPT_OLD = '"leixing":"bug/优化(无法判定填待确认)"}'
PROMPT_NEW = '"leixing":"bug/优化(无法判定填待确认)","search_keyword":"2-6字核心问题词,用于查重搜已有记录(如扫码/离线/支付失败/订单结束),取最核心名词或动宾,不同客户对同类问题应输出相同词"}'

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

NEW_6250_JUDGE_OUTPUTS = {
    "label": {"children": None, "type": "string"},
    "mokuai": {"children": None, "type": "string"},
    "caozuomiaoshu": {"children": None, "type": "string"},
    "huanjing": {"children": None, "type": "string"},
    "leixing": {"children": None, "type": "string"},
    "search_keyword": {"children": None, "type": "string"},
}

NEW_6240BUILD_CODE = r'''def main(mokuai: str, search_keyword: str) -> dict:
    import json
    kw = (search_keyword or "").strip() or (mokuai or "").strip()
    return {"body_json": json.dumps({"keyword": kw, "limit": 5}, ensure_ascii=False)}'''

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(PATH, encoding="utf-8") as f:
    data = yaml.load(f)

cnt = []
for n in data["workflow"]["graph"]["nodes"]:
    nid = n.get("id")
    d = n.get("data", {})
    if nid == "6250":
        pts = d.get("prompt_template", [])
        if pts and isinstance(pts[0].get("text"), str) and PROMPT_OLD in pts[0]["text"]:
            pts[0]["text"] = pts[0]["text"].replace(PROMPT_OLD, PROMPT_NEW, 1)
            cnt.append("6250:prompt")
    elif nid == "6250-judge":
        d["code"] = NEW_6250_JUDGE_CODE
        d["outputs"] = NEW_6250_JUDGE_OUTPUTS
        cnt.append("6250-judge")
    elif nid == "6240build":
        d["code"] = NEW_6240BUILD_CODE
        vars_ = d.get("variables", [])
        if not any(v.get("variable") == "search_keyword" for v in vars_):
            vars_.append({"variable": "search_keyword", "value_selector": ["6250-judge", "search_keyword"]})
            d["variables"] = vars_
        cnt.append("6240build")

with open(PATH, "w", encoding="utf-8") as f:
    yaml.dump(data, f)
print("synced: %s" % cnt)
