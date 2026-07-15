#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 #7 改动到本地 charge_charging_A.yml(L1 加 out-of-domain)。复用 patch_7_a.patch_graph。"""
import sys
from ruamel.yaml import YAML

sys.path.insert(0, ".")
from patch_7_a import patch_graph  # noqa

YML = "charge_charging_A.yml"
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
with open(YML, "r", encoding="utf-8") as f:
    doc = yaml.load(f)
g = doc["workflow"]["graph"]
touched = patch_graph(g)
with open(YML, "w", encoding="utf-8") as f:
    yaml.dump(doc, f)
print("synced:", touched)
