#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 统一查表修复2: 6250-if 改读 cv_sufficiency_label (避免引用未运行的 6250-judge)

问题: 统一查表后补充/否认未命中也到 6250-if, 但 6250-if 条件读 [6250-judge,label];
      补充跑 6250b-judge、否认跑 6177, 6250-judge 没跑 -> 变量不存在 -> if-else 报错。
修复: 6250-if 改读会话变量 cv_sufficiency_label (始终存在), 三入口分别设值:
  - 6243-pre (首次): = [6250-judge, label]
  - 6243b (补充): = [6250b-judge, label]
  - 6177-assigner (否认): = [6901, str_sufficient] (新增常量 SUFFICIENT)
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


def find_node(nid):
    for n in nodes:
        if n['id'] == nid:
            return n
    raise KeyError('node not found: ' + nid)


def out_str():
    return {'children': None, 'type': 'string'}


# 1. 加 cv_sufficiency_label 会话变量
cv_vars = data['workflow']['conversation_variables']
if not any(cv.get('name') == 'cv_sufficiency_label' for cv in cv_vars):
    cv_vars.append({
        'description': '充足度标签(SUFFICIENT/INSUFFICIENT), 6250-if 读取(避免引用未运行节点)',
        'id': 'a1b2c3d4-0001-4000-8000-000000000005',
        'name': 'cv_sufficiency_label',
        'value': '',
        'value_type': 'string',
    })

# 2. 6901 加 str_sufficient 常量
n6901 = find_node('6901')
if '"str_sufficient"' not in n6901['data']['code']:
    n6901['data']['code'] = n6901['data']['code'].replace(
        '"clarify_count_1": 1\n    }',
        '"clarify_count_1": 1,\n        "str_sufficient": "SUFFICIENT"\n    }'
    )
    n6901['data']['outputs']['str_sufficient'] = out_str()

# 3. 6243-pre 加 cv_sufficiency_label = [6250-judge, label]
n6243pre = find_node('6243-pre')
if not any(it['variable_selector'] == ['conversation', 'cv_sufficiency_label'] for it in n6243pre['data']['items']):
    n6243pre['data']['items'].append({
        'input_type': 'variable', 'operation': 'over-write',
        'value': ['6250-judge', 'label'],
        'variable_selector': ['conversation', 'cv_sufficiency_label'],
    })

# 4. 6243b 加 cv_sufficiency_label = [6250b-judge, label]
n6243b = find_node('6243b')
if not any(it['variable_selector'] == ['conversation', 'cv_sufficiency_label'] for it in n6243b['data']['items']):
    n6243b['data']['items'].append({
        'input_type': 'variable', 'operation': 'over-write',
        'value': ['6250b-judge', 'label'],
        'variable_selector': ['conversation', 'cv_sufficiency_label'],
    })

# 5. 6177-assigner 加 cv_sufficiency_label = [6901, str_sufficient]
n6177a = find_node('6177-assigner')
if not any(it['variable_selector'] == ['conversation', 'cv_sufficiency_label'] for it in n6177a['data']['items']):
    n6177a['data']['items'].append({
        'input_type': 'variable', 'operation': 'over-write',
        'value': ['6901', 'str_sufficient'],
        'variable_selector': ['conversation', 'cv_sufficiency_label'],
    })

# 6. 6250-if sufficient/insufficient 改读 [conversation, cv_sufficiency_label]
n6250if = find_node('6250-if')
for case in n6250if['data']['cases']:
    if case['case_id'] in ('sufficient', 'insufficient'):
        for cond in case['conditions']:
            if cond.get('variable_selector') == ['6250-judge', 'label']:
                cond['variable_selector'] = ['conversation', 'cv_sufficiency_label']

with open(OUT, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
import ast
ast.parse(n6901['data']['code'])
assert 'cv_sufficiency_label' in [cv.get('name') for cv in cv_vars]
assert 'str_sufficient' in n6901['data']['outputs']
assert any(it['variable_selector'] == ['conversation', 'cv_sufficiency_label'] for it in n6243pre['data']['items'])
assert any(it['variable_selector'] == ['conversation', 'cv_sufficiency_label'] for it in n6243b['data']['items'])
assert any(it['variable_selector'] == ['conversation', 'cv_sufficiency_label'] for it in n6177a['data']['items'])
for case in n6250if['data']['cases']:
    if case['case_id'] in ('sufficient', 'insufficient'):
        assert case['conditions'][0]['variable_selector'] == ['conversation', 'cv_sufficiency_label']
# 无残留 [6250-judge, label] 在 6250-if
assert not any(c.get('variable_selector') == ['6250-judge', 'label']
               for case in n6250if['data']['cases'] for c in case.get('conditions', []))

print('B.yml fix2 applied:', OUT)
print('cv_sufficiency_label added')
print('6901 str_sufficient:', 'str_sufficient' in n6901['data']['outputs'])
print('6243-pre sets label:', any(it['variable_selector']==['conversation','cv_sufficiency_label'] for it in n6243pre['data']['items']))
print('6243b sets label:', any(it['variable_selector']==['conversation','cv_sufficiency_label'] for it in n6243b['data']['items']))
print('6177-assigner sets label:', any(it['variable_selector']==['conversation','cv_sufficiency_label'] for it in n6177a['data']['items']))
print('6250-if reads cv:', [c['conditions'][0]['variable_selector'] for c in n6250if['data']['cases'] if c['case_id'] in ('sufficient','insufficient')])
