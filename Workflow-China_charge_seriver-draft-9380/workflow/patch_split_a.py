#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 v24.yml 拆出 App A (KB问答, 无 bug 状态) → charge_charging_A.yml

A = L1(6101)+L3 A/B/C(6201+6210-6231)+FAQ(6102-6111)+澄清流(6003/6004/6104)
改动:
  - 移除所有 B 节点(状态机/D路径/6162*/6239/6250*/6260*/6170x/6176/6177/6240-6244)
  - 6002→6601 改 6002→6003 (A 无状态机, 入口直达 L1)
  - 6201 class_d(原→6250) 改 →6201-switch-bug(发 SWITCH_TO_BUG 标记)→6098
  - 6098 聚合器只留 A 分支末尾 + 6201-switch-bug
  - cv 全保留(安全)
"""
from ruamel.yaml import YAML

V24 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v24.yml'
OUT = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_A.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V24) as f:
    data = yaml.load(f)

graph = data['workflow']['graph']
nodes = graph['nodes']
edges = graph['edges']

B_ONLY = {
    '6601','6162','6162-abort','6162-out','6170','6170-parse','6170b','6170c','6170d',
    '6171','6171b','6171c','6171d','6172','6173','6173-assigner','6173-timer','6175',
    '6175-assigner','6175-parse','6175-timer','6176a','6176b','6176c','6176d','6177',
    '6177-assigner','6177-parse','6239-if','6239-llm','6239-modify-assigner','6239-new-idle',
    '6239-trans','6239-trans-parse','6240','6240-denial','6240-denial-parse','6240-parse',
    '6240build','6240builddnl','6241','6241-denial','6242','6242-denial','6242b','6242b-denial',
    '6242c','6243','6243b','6244','6244-timer','6250','6250-if','6250-insuf','6250-insuf-out',
    '6250-judge','6250b','6250b-if','6250b-insuf','6250b-insuf-out','6250b-judge','6250b-parse',
    '6260a','6260b','6260c','6261','6262','6262b',
}


def pos(x, y):
    return {'x': x, 'y': y}


def out_str():
    return {'children': None, 'type': 'string'}


def code(nid, title, code_str, outputs, variables, x, y):
    return {
        'data': {'code': code_str, 'code_language': 'python3', 'outputs': outputs,
                 'selected': False, 'title': title, 'type': 'code', 'variables': variables},
        'height': 88, 'id': nid, 'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def edge(eid, src, tgt, sh, st, tt, th='target'):
    return {'data': {'sourceType': st, 'targetType': tt}, 'id': eid, 'source': src,
            'sourceHandle': sh, 'target': tgt, 'targetHandle': th, 'type': 'custom'}


# 1. 移除 B 节点 + 相关边
nodes[:] = [n for n in nodes if n['id'] not in B_ONLY]
edges[:] = [e for e in edges if e['source'] not in B_ONLY and e['target'] not in B_ONLY]

# 2. 6002→6601 改 6002→6003 (6601 已移除, 6002→6601 边已随上面删除)
edges.append(edge('e-6002-6003', '6002', '6003', 'source', 'code', 'if-else'))

# 3. 6201 class_d → 6201-switch-bug → 6098
CODE_SWITCH_BUG = (
    'def main() -> dict:\n'
    '    return {"answer_text": "<!--SYS:SWITCH_TO_BUG-->"}\n'
)
nodes.append(code('6201-switch-bug', '切换bug模块(发标记)', CODE_SWITCH_BUG,
                  {'answer_text': out_str()}, [], 480, 520))
# 6201[class_d]→6250 边已随 6250 移除; 加新边
edges.append(edge('e-6201-d-switch', '6201', '6201-switch-bug', 'class_d', 'question-classifier', 'code'))
edges.append(edge('e-6201-switch-6098', '6201-switch-bug', '6098', 'source', 'code', 'answer'))

# 4. 6098 聚合器只留 A 分支 + 6201-switch-bug
n6098 = next(n for n in nodes if n['id'] == '6098')
n6098['data']['variables'] = [
    ['6105', 'text'], ['6107', 'text'], ['6111', 'text'],
    ['6212', 'text'], ['6221', 'text'], ['6231', 'text'],
    ['6201-switch-bug', 'answer_text'],
]

# 5. app name
if 'app' in data:
    data['app']['name'] = 'charge_charging_A_kbqa'
    data['app']['description'] = 'App A: 知识库问答 (L1+L3 A/B/C+FAQ), 无 bug 状态机'

with open(OUT, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
idset = set(n['id'] for n in nodes)
# 节点 id 唯一
assert len([n for n in nodes]) == len(idset), 'duplicate node id'
# 边端点存在
for e in edges:
    assert e['source'] in idset and e['target'] in idset, 'dangling edge: ' + e['id'] + ' ('+e['source']+'->'+e['target']+')'
# 无 B 节点残留
assert not (B_ONLY & idset), 'B node leaked: ' + str(B_ONLY & idset)
# 6201-switch-bug 在
assert '6201-switch-bug' in idset
# 6002→6003
assert any(e['source'] == '6002' and e['target'] == '6003' for e in edges)
# 6201 class_d→6201-switch-bug
assert any(e['source'] == '6201' and e['sourceHandle'] == 'class_d' and e['target'] == '6201-switch-bug' for e in edges)

# 全量扫描变量引用: 所有 value_selector/variable_selector 引用的节点必须存在
def scan_refs(d, leaks):
    if isinstance(d, dict):
        for k, v in d.items():
            if k in ('value_selector', 'variable_selector') and isinstance(v, list) and v:
                if v[0] not in ('conversation', 'sys') and v[0] not in idset:
                    leaks.add(tuple(v))
            else:
                scan_refs(v, leaks)
    elif isinstance(d, list):
        for x in d:
            scan_refs(x, leaks)

leaks = set()
for n in nodes:
    scan_refs(n['data'], leaks)
# 6098 aggregator variables 也扫
for vv in n6098['data']['variables']:
    if isinstance(vv, list) and vv and vv[0] not in ('conversation', 'sys') and vv[0] not in idset:
        leaks.add(tuple(vv))
assert not leaks, 'dangling variable refs: ' + str(leaks)

# if-else 每 case 有出边 (除 6901 常量/6099 终点)
for n in nodes:
    if n['data'].get('type') == 'if-else':
        for c in n['data'].get('cases', []):
            cid = c.get('case_id')
            if cid == 'default':
                continue
            # default 必须有出边
        # 至少有一个 case 出边
        assert any(e['source'] == n['id'] for e in edges), 'if-else no out edge: ' + n['id']

print('A.yml generated:', OUT)
print('nodes:', len(nodes), 'edges:', len(edges))
print('leaks:', leaks if leaks else 'none')
