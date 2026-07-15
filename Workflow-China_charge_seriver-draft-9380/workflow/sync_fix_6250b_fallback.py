#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 6250b-judge 移除 FALLBACK 到本地 charge_charging_B.yml。"""
from ruamel.yaml import YAML

YML = "charge_charging_B.yml"
NEW_CODE = r'''def main(llm_text: str, clarify_count) -> dict:
    import re
    text = llm_text or ""
    t = text.upper()
    if "INSUFFICIENT" in t or "NOT SUFFICIENT" in t:
        is_suf = False
    elif "SUFFICIENT" in t:
        is_suf = True
    else:
        is_suf = False
    try:
        count = int(clarify_count or 0)
    except Exception:
        count = 0
    if is_suf:
        return {"label": "SUFFICIENT", "next_count": count}
    return {"label": "INSUFFICIENT", "next_count": count + 1}'''

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
with open(YML, "r", encoding="utf-8") as f:
    doc = yaml.load(f)
for n in doc["workflow"]["graph"]["nodes"]:
    if n.get("id") == "6250b-judge":
        old = n["data"].get("code", "")
        if "FALLBACK" in old and "count >= 2" in old:
            n["data"]["code"] = NEW_CODE
            print("patched 6250b-judge: remove FALLBACK")
        elif "FALLBACK" not in old:
            print("already no FALLBACK")
with open(YML, "w", encoding="utf-8") as f:
    yaml.dump(doc, f)
print("done")
