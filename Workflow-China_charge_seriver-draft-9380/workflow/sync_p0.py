#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 P0 改动到本地 charge_charging_B.yml。复用 patch_p0.patch_graph(graph 部分) +
单独处理 yml 的 conversation_variables(list 格式, 与 DB dict 不同)。"""
import sys
from ruamel.yaml import YAML

sys.path.insert(0, ".")
from patch_p0 import patch_graph, CV_SEARCH  # noqa

YML = "charge_charging_B.yml"
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
with open(YML, "r", encoding="utf-8") as f:
    doc = yaml.load(f)
touched = patch_graph(doc["workflow"]["graph"])
# yml conversation_variables 是 list of {description,id,name,value,value_type}
cvs = doc["workflow"]["conversation_variables"]
if not any(cv.get("name") == "cv_search_keyword" for cv in cvs):
    cvs.append({
        "description": CV_SEARCH["description"],
        "id": CV_SEARCH["id"],
        "name": "cv_search_keyword",
        "value": "",
        "value_type": "string",
    })
    touched.append("conv_vars:+cv_search_keyword")
with open(YML, "w", encoding="utf-8") as f:
    yaml.dump(doc, f)
print("synced:", touched)
