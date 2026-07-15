#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""缺口1 patch: 从 v20.yml 生成 v21.yml (D4 命中汇报模板化,去 LLM)

目标: 按 06-customer-feedback-flow.md 5.1 双分支 LLM 策略——命中 bug 表用预设模板,
不需要大模型。6242 D4 当前是 LLM(每次命中都调 Doubao),改为 code 模板拼接 row_summary。

改:
  1. 6242: type llm → code, 读 [6240-parse, row_summary], 输出 answer_text (模板话术)
  2. 6242c: variables llm_text 的 value_selector [6242, text] → [6242, answer_text]
  3. 6098 聚合器: 移除 stale 的 [6242, text]
     (6242→6242b→6242c→6098, 6242 无直连 6098 边; 转 code 后无 text 输出会变悬空引用)

不变: 6242b assigner(设 cv_record_id/cv_row_summary/await_confirm_identity)、
      6242c 的 TIMER 标记拼接、6242c→6098 边
"""
from ruamel.yaml import YAML

V20 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v20.yml'
V21 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v21.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V20) as f:
    data = yaml.load(f)

graph = data['workflow']['graph']
nodes = graph['nodes']
edges = graph['edges']


def find_node(nid):
    for n in nodes:
        if n['id'] == nid:
            return n
    raise KeyError('node not found: ' + nid)


def pos(x, y):
    return {'x': x, 'y': y}


def out_str():
    return {'children': None, 'type': 'string'}


# ==================== 1. 6242: llm → code (模板拼接 row_summary) ====================
CODE_6242 = (
    'def main(row_summary: str) -> dict:\n'
    '    s = (row_summary or "").strip()\n'
    '    if not s:\n'
    '        s = "该记录内容"\n'
    '    return {"answer_text": "我们查询到已有相关追踪记录:\\n" + s + "\\n\\n请问这是您反馈的问题吗？"}\n'
)
n6242 = find_node('6242')
# 原 6242 position: x=1960, y=700
n6242['data'] = {
    'code': CODE_6242, 'code_language': 'python3',
    'outputs': {'answer_text': out_str()},
    'selected': False, 'title': 'D4 命中汇报(模板)', 'type': 'code',
    'variables': [{'variable': 'row_summary', 'value_selector': ['6240-parse', 'row_summary']}],
}
# height/width/position/id 保持不变

# ==================== 2. 6242c: value_selector [6242, text] → [6242, answer_text] ====================
n6242c = find_node('6242c')
for v in n6242c['data']['variables']:
    if v['variable'] == 'llm_text' and v['value_selector'] == ['6242', 'text']:
        v['value_selector'] = ['6242', 'answer_text']

# ==================== 3. 6098 聚合器: 移除 stale 的 [6242, text] ====================
n6098 = find_node('6098')
n6098['data']['variables'] = [vv for vv in n6098['data']['variables']
                              if not (isinstance(vv, list) and len(vv) >= 2 and vv[0] == '6242' and vv[1] == 'text')]

# ==================== dump ====================
with open(V21, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
ids = [n['id'] for n in nodes]
assert len(ids) == len(set(ids)), 'duplicate node id'
# 6242 已是 code
assert find_node('6242')['data']['type'] == 'code', '6242 not code'
# 6242c 读 6242.answer_text
assert n6242c['data']['variables'][0]['value_selector'] == ['6242', 'answer_text']
# 6098 不再有 6242.text
assert not any(isinstance(vv, list) and vv == ['6242', 'text'] for vv in n6098['data']['variables'])
# 6242c 仍在 6098 (真实路径)
assert any(isinstance(vv, list) and vv == ['6242c', 'answer_text'] for vv in n6098['data']['variables'])
# 边端点都存在
idset = set(ids)
for e in edges:
    assert e['source'] in idset and e['target'] in idset, 'dangling edge: ' + e['id']

print('v21 generated:', V21)
print('nodes:', len(nodes), 'edges:', len(edges))
print('6242 type:', find_node('6242')['data']['type'])
print('6242c reads:', n6242c['data']['variables'][0]['value_selector'])
print('6098 vars count:', len(n6098['data']['variables']))
