#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地 charge_charging_A.yml / charge_charging_B.yml 的 7 个分类器节点
同步加上 memory 块(与 124 已部署一致,根因1)。ruamel 方式,项目惯例(patch_split_b.py 同款)。"""
from ruamel.yaml import YAML

WF = "/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow"
TARGETS = {
    f"{WF}/charge_charging_A.yml": ["6101", "6201"],
    f"{WF}/charge_charging_B.yml": ["6170", "6170b", "6170c", "6170d", "6239-llm"],
}
MEM = {"window": {"enabled": True, "size": 10}}

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

for path, ids in TARGETS.items():
    with open(path, encoding="utf-8") as f:
        data = yaml.load(f)
    nodes = data["workflow"]["graph"]["nodes"]
    cnt = 0
    for n in nodes:
        if n.get("id") in ids:
            n["data"]["memory"] = MEM
            cnt += 1
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    print("%s: patched %d nodes" % (path.split("/")[-1], cnt))
