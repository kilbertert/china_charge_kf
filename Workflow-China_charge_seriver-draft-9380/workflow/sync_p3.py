#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 patch_p3 到本地 charge_charging_B.yml。"""
import sys
from ruamel.yaml import YAML

sys.path.insert(0, ".")
from patch_p3 import patch_graph  # noqa

YML = "charge_charging_B.yml"
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
with open(YML, "r", encoding="utf-8") as f:
    doc = yaml.load(f)
touched = patch_graph(doc["workflow"]["graph"])
with open(YML, "w", encoding="utf-8") as f:
    yaml.dump(doc, f)
print("synced:", touched)
