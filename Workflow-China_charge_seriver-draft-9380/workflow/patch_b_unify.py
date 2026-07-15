#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 工作流统一查表修复 (问题1): 补充/否认也查表比对, 避免重复录入

根因: MODIFY_NEW 补充路径 6250b-parse->6243b->6244(确认) 不查表; denial 用独立重复链。
修复: 统一 6240build 读 cv_mokuai, 三个入口(首次/补充/否认)都先设 cv_mokuai 再共享 6240build->6240->6240-parse->6241 链。删除 Gap2 denial 重复链(6节点)。

改:
  1. 6240build: mokuai 来源 [6250-judge,mokuai] -> [conversation,cv_mokuai]
  2. 6243: 删 4 个 cv 字段项(改由 6243-pre/6243b/6177-assigner 设, 避免补充/否认路径覆盖空)
  3. 新增 6243-pre(assigner): 首次反馈从 6250-judge 设 cv 四字段
  4. 边: 6250-judge->6243-pre->6240build; 6243b->6240build; 6177-assigner->6240build
     删 6250-judge->6240build, 6243b->6244, 6177-assigner->6240builddnl
     删 denial 链 6 节点(6240builddnl/6240-denial/6240-denial-parse/6241-denial/6242b-denial/6242-denial)+其边
  5. 6098: 移除 [6242-denial, answer_text]
"""
from ruamel.yaml import YAML

SRC = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_B.yml'
OUT = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_B.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(SRC) as f:
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


def assigner(nid, title, items, x, y):
    return {
        'data': {'items': items, 'selected': False, 'title': title, 'type': 'assigner', 'version': '2'},
        'height': 88, 'id': nid, 'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def edge(eid, src, tgt, sh, st, tt, th='target'):
    return {'data': {'sourceType': st, 'targetType': tt}, 'id': eid, 'source': src,
            'sourceHandle': sh, 'target': tgt, 'targetHandle': th, 'type': 'custom'}


DENIAL_NODES = {'6240builddnl', '6240-denial', '6240-denial-parse',
                '6241-denial', '6242b-denial', '6242-denial'}

# 1. 6240build 读 cv_mokuai
n6240build = find_node('6240build')
for v in n6240build['data']['variables']:
    if v['variable'] == 'mokuai':
        v['value_selector'] = ['conversation', 'cv_mokuai']

# 2. 6243 删 4 个 cv 字段项
n6243 = find_node('6243')
n6243['data']['items'] = [
    it for it in n6243['data']['items']
    if it['variable_selector'][1] not in ('cv_mokuai', 'cv_huanjing', 'cv_leixing', 'cv_feedback_zh')
]

# 3. 新增 6243-pre (首次反馈设 cv 四字段 from 6250-judge)
nodes.append(assigner('6243-pre', 'var_首次反馈设cv四字段', [
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6250-judge', 'mokuai'],
     'variable_selector': ['conversation', 'cv_mokuai']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6250-judge', 'huanjing'],
     'variable_selector': ['conversation', 'cv_huanjing']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6250-judge', 'leixing'],
     'variable_selector': ['conversation', 'cv_leixing']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6250-judge', 'caozuomiaoshu'],
     'variable_selector': ['conversation', 'cv_feedback_zh']},
], 1180, 620))

# 4. 删 denial 链节点 + 相关边
nodes[:] = [n for n in nodes if n['id'] not in DENIAL_NODES]
edges[:] = [e for e in edges
            if e['source'] not in DENIAL_NODES and e['target'] not in DENIAL_NODES]
# 删 6250-judge->6240build, 6243b->6244
edges[:] = [e for e in edges
            if not ((e['source'] == '6250-judge' and e['target'] == '6240build')
                    or (e['source'] == '6243b' and e['target'] == '6244'))]

# 5. 加新边
for e in [
    edge('e-6250judge-6243pre', '6250-judge', '6243-pre', 'source', 'code', 'variable-assigner'),
    edge('e-6243pre-6240build', '6243-pre', '6240build', 'source', 'variable-assigner', 'code'),
    edge('e-6243b-6240build', '6243b', '6240build', 'source', 'variable-assigner', 'code'),
    edge('e-6177a-6240build', '6177-assigner', '6240build', 'source', 'variable-assigner', 'code'),
]:
    edges.append(e)

# 6. 6098 移除 [6242-denial, answer_text]
n6098 = find_node('6098')
n6098['data']['variables'] = [vv for vv in n6098['data']['variables']
                              if not (isinstance(vv, list) and vv == ['6242-denial', 'answer_text'])]

with open(OUT, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
idset = set(n['id'] for n in nodes)
assert len([n for n in nodes]) == len(idset), 'dup id'
for e in edges:
    assert e['source'] in idset and e['target'] in idset, 'dangling edge: ' + e['id']
assert not (DENIAL_NODES & idset), 'denial node leaked: ' + str(DENIAL_NODES & idset)
# 6240build 读 cv_mokuai
assert n6240build['data']['variables'][0]['value_selector'] == ['conversation', 'cv_mokuai']
# 6243 无 cv 字段项
assert all(it['variable_selector'][1] not in ('cv_mokuai', 'cv_huanjing', 'cv_leixing', 'cv_feedback_zh')
           for it in n6243['data']['items'])
# 6243-pre 存在, 入口三连
assert '6243-pre' in idset
assert any(e['source'] == '6250-judge' and e['target'] == '6243-pre' for e in edges)
assert any(e['source'] == '6243-pre' and e['target'] == '6240build' for e in edges)
assert any(e['source'] == '6243b' and e['target'] == '6240build' for e in edges)
assert any(e['source'] == '6177-assigner' and e['target'] == '6240build' for e in edges)
# 6242c 仍在 6098 (hit 路径)
assert ['6242c', 'answer_text'] in n6098['data']['variables']
assert ['6242-denial', 'answer_text'] not in n6098['data']['variables']
# 全量变量引用扫描
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
assert not leaks, 'dangling refs: ' + str(leaks)

print('B.yml unified:', OUT)
print('nodes:', len(nodes), 'edges:', len(edges))
print('6240build reads:', n6240build['data']['variables'][0]['value_selector'])
print('6243 items:', [it['variable_selector'][1] for it in n6243['data']['items']])
print('denial nodes removed:', not (DENIAL_NODES & idset))
print('leaks:', leaks if leaks else 'none')
