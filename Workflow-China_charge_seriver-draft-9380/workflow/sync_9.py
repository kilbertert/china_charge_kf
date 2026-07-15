#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 #9 改动到本地 charge_charging_B.yml(3 HTTP 节点删 Authorization)。"""
from ruamel.yaml import YAML

YML = "charge_charging_B.yml"
TARGETS = ["6240", "6260b", "6176b"]
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
with open(YML, "r", encoding="utf-8") as f:
    doc = yaml.load(f)
for n in doc["workflow"]["graph"]["nodes"]:
    if n.get("id") in TARGETS:
        d = n["data"]
        h = d.get("headers", "")
        if isinstance(h, str) and "Authorization" in h:
            d["headers"] = "Content-Type:application/json"
            print("strip", n["id"])
with open(YML, "w", encoding="utf-8") as f:
    yaml.dump(doc, f)
print("done")
