#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 v24.yml 拆出 App B (bug追踪, 有 cv_flow_state) → charge_charging_B.yml

B = D路径 + 状态机(6601/6170x/6240-6262/6250*/6239/6162*/6176/6177)
改动:
  - 移除 A 节点(6003/6004/6101/6102-6111/6201/6210-6231)
  - 6601[default](原→6003) 改 →6250 (IDLE 直达 N5, B 不做 L1/L3)
  - 6162(原→6003 re-entry) 改 →6162-switch-kb(发 SWITCH_TO_KB_REENTRY)→6098
  - 6239-new-idle(原→6003) 改 →6239-switch-kb(发 SWITCH_TO_KB_REENTRY)→6098
  - 6162-out 追加 SWITCH_TO_KB_DONE 标记
  - 6098 聚合器只留 B 分支 + 2 个 switch-kb
  - cv 全保留
"""
from ruamel.yaml import YAML

V24 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v24.yml'
OUT = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_B.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V24) as f:
    data = yaml.load(f)

graph = data['workflow']['graph']
nodes = graph['nodes']
edges = graph['edges']

A_ONLY = {
    '6003', '6004', '6101', '6102', '6103-if', '6103-llm', '6103-parse', '6104',
    '6105', '6106', '6107', '6108', '6110', '6111', '6201', '6210', '6211', '6212',
    '6220', '6221', '6230', '6231',
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


# 1. 移除 A 节点 + 相关边
nodes[:] = [n for n in nodes if n['id'] not in A_ONLY]
edges[:] = [e for e in edges if e['source'] not in A_ONLY and e['target'] not in A_ONLY]

# 2. 6601[default] →6250 (原→6003 已随 6003 移除)
edges.append(edge('e-6601-default-6250', '6601', '6250', 'default', 'if-else', 'llm'))

# 3. 6162 →6162-switch-kb →6098 (原→6003 已移除)
CODE_SWITCH_REENTRY = (
    'def main() -> dict:\n'
    '    return {"answer_text": "<!--SYS:SWITCH_TO_KB_REENTRY-->"}\n'
)
nodes.append(code('6162-switch-kb', '切换KB模块(IRRELEVANT)', CODE_SWITCH_REENTRY,
                  {'answer_text': out_str()}, [], 300, 760))
edges.append(edge('e-6162-switch', '6162', '6162-switch-kb', 'source', 'variable-assigner', 'code'))
edges.append(edge('e-6162-switch-6098', '6162-switch-kb', '6098', 'source', 'code', 'answer'))

# 4. 6239-new-idle →6239-switch-kb →6098 (原→6003 已移除)
nodes.append(code('6239-switch-kb', '切换KB模块(修改窗NEW)', CODE_SWITCH_REENTRY,
                  {'answer_text': out_str()}, [], 100, 980))
edges.append(edge('e-6239newid-switch', '6239-new-idle', '6239-switch-kb', 'source', 'variable-assigner', 'code'))
edges.append(edge('e-6239-switch-6098', '6239-switch-kb', '6098', 'source', 'code', 'answer'))

# 5. 6162-out 追加 SWITCH_TO_KB_DONE
n6162out = next(n for n in nodes if n['id'] == '6162-out')
n6162out['data']['code'] = (
    'def main() -> dict:\n'
    '    text = "好的,本次反馈就到这里啦。若还有其他问题,随时联系我为您处理哦~"\n'
    '    return {"answer_text": text + "\\n<!--SYS:TIMER|action=cancel-->\\n<!--SYS:SWITCH_TO_KB_DONE-->"}\n'
)

# 6. 6098 聚合器只留 B 分支 + 2 switch-kb
n6098 = next(n for n in nodes if n['id'] == '6098')
n6098['data']['variables'] = [
    ['6244-timer', 'answer_text'], ['6262b', 'answer_text'], ['6242c', 'answer_text'],
    ['6173-timer', 'answer_text'], ['6175-timer', 'answer_text'], ['6176d', 'answer_text'],
    ['6250-insuf-out', 'answer_text'], ['6250b-insuf-out', 'answer_text'],
    ['6162-out', 'answer_text'], ['6242-denial', 'answer_text'],
    ['6162-switch-kb', 'answer_text'], ['6239-switch-kb', 'answer_text'],
]

# 7. app name
if 'app' in data:
    data['app']['name'] = 'charge_charging_B_bugtrack'
    data['app']['description'] = 'App B: bug反馈记录追踪 (D路径状态机), 有 cv_flow_state'

with open(OUT, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
idset = set(n['id'] for n in nodes)
assert len([n for n in nodes]) == len(idset), 'duplicate node id'
for e in edges:
    assert e['source'] in idset and e['target'] in idset, 'dangling edge: ' + e['id'] + ' ('+e['source']+'->'+e['target']+')'
assert not (A_ONLY & idset), 'A node leaked: ' + str(A_ONLY & idset)
assert '6162-switch-kb' in idset and '6239-switch-kb' in idset
# 6601[default]→6250
assert any(e['source'] == '6601' and e['sourceHandle'] == 'default' and e['target'] == '6250' for e in edges)
# 6162→6162-switch-kb, 6239-new-idle→6239-switch-kb
assert any(e['source'] == '6162' and e['target'] == '6162-switch-kb' for e in edges)
assert any(e['source'] == '6239-new-idle' and e['target'] == '6239-switch-kb' for e in edges)
# 6162-out 含 SWITCH_TO_KB_DONE
assert 'SWITCH_TO_KB_DONE' in n6162out['data']['code']
# 6002→6601 仍在 (B 保留 6601)
assert any(e['source'] == '6002' and e['target'] == '6601' for e in edges)

# 全量扫描变量引用
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
for vv in n6098['data']['variables']:
    if isinstance(vv, list) and vv and vv[0] not in ('conversation', 'sys') and vv[0] not in idset:
        leaks.add(tuple(vv))
assert not leaks, 'dangling variable refs: ' + str(leaks)

# if-else 至少有出边
for n in nodes:
    if n['data'].get('type') == 'if-else':
        assert any(e['source'] == n['id'] for e in edges), 'if-else no out edge: ' + n['id']

print('B.yml generated:', OUT)
print('nodes:', len(nodes), 'edges:', len(edges))
print('leaks:', leaks if leaks else 'none')
