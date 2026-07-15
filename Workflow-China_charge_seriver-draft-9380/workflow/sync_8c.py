#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 #8-c 改动到本地 charge_charging_B.yml(6250b-parse FALLBACK 分支)。"""
from ruamel.yaml import YAML

YML = "charge_charging_B.yml"

NEW_6250B_PARSE_CODE = r'''def main(llm_text: str, label: str) -> dict:
    import json, re
    if label == "FALLBACK":
        return {"mokuai":"待人工核实","caozuomiaoshu":"用户多次补充后信息仍不完整,需人工跟进核实具体问题","huanjing":"待确认","leixing":"bug"}
    text = llm_text or ""
    m = re.search(r"\{[^{}]*\}", text)
    if not m:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}
    try:
        obj = json.loads(m.group(0))
        return {
            "mokuai": str(obj.get("mokuai","")).strip()[:50],
            "caozuomiaoshu": str(obj.get("caozuomiaoshu","")).strip()[:500],
            "huanjing": str(obj.get("huanjing","")).strip()[:20],
            "leixing": str(obj.get("leixing","")).strip()[:20]
        }
    except Exception:
        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}'''


def main():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(YML, "r", encoding="utf-8") as f:
        doc = yaml.load(f)
    for n in doc["workflow"]["graph"]["nodes"]:
        if n.get("id") == "6250b-parse":
            d = n.get("data")
            if "待确认" in d.get("code", "") and 'label == "FALLBACK"' in d.get("code", ""):
                d["code"] = NEW_6250B_PARSE_CODE
                print("synced: 6250b-parse:FALLBACK 待确认->待人工核实")
            elif "待人工核实" in d.get("code", ""):
                print("already synced")
            with open(YML, "w", encoding="utf-8") as f:
                yaml.dump(doc, f)
            return
    print("6250b-parse NOT FOUND")


main()
