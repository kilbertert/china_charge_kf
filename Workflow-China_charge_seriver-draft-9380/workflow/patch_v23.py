#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""缺口5 patch (混合方案): 从 v22.yml 生成 v23.yml (区分 ABANDON/新话题, 加结束话术)

探针发现: 当前 IRRELEVANT/default 路径是 re-entry 重处理(非静默)。
- "算了不报了" → re-entry 当新反馈引导(差)
- "我想查订单" 等真新话题 → re-entry 正常处理(好)

混合方案: LLM 增判 ABANDON(放弃/结束) vs 新话题。
- ABANDON / DENY_MODIFY(6170c) → 结束话术 + reset IDLE + end (新增 6162-abort + 6162-out)
- IRRELEVANT/default(新话题) → 保留 re-entry (default→6162→6003, 不动)

改:
  1. 6170/6170b/6170c/6170d prompt 加 ABANDON 标签
  2. 6170-parse label 列表加 ABANDON
  3. 6171/6171b/6171c/6171d 加 abandon case → 6162-abort; 6171c 额外加 deny_modify case → 6162-abort
  4. 新增 6162-abort (assigner reset IDLE, mirror 6162 items) + 6162-out (code 中性结束话术)
  5. 加边: 5 条 case→6162-abort + 6162-abort→6162-out + 6162-out→6098
  6. 6098 加 [6162-out, answer_text]
"""
from ruamel.yaml import YAML

V22 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v22.yml'
V23 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v23.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V22) as f:
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


def code(nid, title, code_str, outputs, variables, x, y):
    return {
        'data': {'code': code_str, 'code_language': 'python3', 'outputs': outputs,
                 'selected': False, 'title': title, 'type': 'code', 'variables': variables},
        'height': 88, 'id': nid, 'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def assigner(nid, title, items, x, y):
    return {
        'data': {'items': items, 'selected': False, 'title': title, 'type': 'assigner', 'version': '2'},
        'height': 88, 'id': nid, 'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def edge(eid, src, tgt, sh, st, tt, th='target'):
    return {'data': {'sourceType': st, 'targetType': tt}, 'id': eid, 'source': src,
            'sourceHandle': sh, 'target': tgt, 'targetHandle': th, 'type': 'custom'}


def insert_before_default(cases_list, new_case):
    for i, c in enumerate(cases_list):
        if c.get('case_id') == 'default':
            cases_list.insert(i, new_case)
            return
    cases_list.append(new_case)


# ==================== 1. 4 个 LLM prompt 加 ABANDON 标签 ====================
ABANDON_LINES = {
    '6170':  '- ABANDON          : 用户要结束/放弃本次反馈,不是开新话题(算了/不报了/没事/不用了/结束吧)',
    '6170b': '- ABANDON          : 用户要结束对话/不继续了(算了/不查了/没事/结束),非否认非开新话题',
    '6170c': '- ABANDON          : 用户要结束对话/不继续了(结束/不查了/没事/再见),非"不用改"非开新话题',
    '6170d': '- ABANDON          : 用户要结束/放弃(算了/没事/不确认了/结束)',
}
for nid, line in ABANDON_LINES.items():
    n = find_node(nid)
    txt = n['data']['prompt_template'][0]['text']
    assert '- IRRELEVANT' in txt, nid + ' missing IRRELEVANT anchor'
    # 在 "- IRRELEVANT" 行前插入 ABANDON 行
    n['data']['prompt_template'][0]['text'] = txt.replace(
        '- IRRELEVANT', line + '\n- IRRELEVANT', 1)

# ==================== 2. 6170-parse label 列表加 ABANDON ====================
n6170p = find_node('6170-parse')
n6170p['data']['code'] = n6170p['data']['code'].replace(
    '"CONFIRM_NEW", "MODIFY_NEW", "MODIFY_EXISTING", "IRRELEVANT"',
    '"CONFIRM_NEW", "MODIFY_NEW", "MODIFY_EXISTING", "ABANDON", "IRRELEVANT"'
)

# ==================== 3. 4 个 if-else 加 abandon case (+ 6171c 加 deny_modify) ====================
# 6171 (用 6170-parse.label, is 比较)
insert_before_default(find_node('6171')['data']['cases'], {
    'case_id': 'abandon', 'logical_operator': 'and',
    'conditions': [{'comparison_operator': 'is', 'id': 'c_ab_6171', 'value': 'ABANDON',
                    'varType': 'string', 'variable_selector': ['6170-parse', 'label']}],
})
# 6171b (contains [6170b, text])
insert_before_default(find_node('6171b')['data']['cases'], {
    'case_id': 'abandon', 'logical_operator': 'and',
    'conditions': [{'comparison_operator': 'contains', 'id': 'c_ab_6171b', 'value': 'ABANDON',
                    'varType': 'string', 'variable_selector': ['6170b', 'text']}],
})
# 6171c: abandon + deny_modify (都→6162-abort)
insert_before_default(find_node('6171c')['data']['cases'], {
    'case_id': 'deny_modify', 'logical_operator': 'and',
    'conditions': [{'comparison_operator': 'contains', 'id': 'c_dm_6171c', 'value': 'DENY_MODIFY',
                    'varType': 'string', 'variable_selector': ['6170c', 'text']}],
})
insert_before_default(find_node('6171c')['data']['cases'], {
    'case_id': 'abandon', 'logical_operator': 'and',
    'conditions': [{'comparison_operator': 'contains', 'id': 'c_ab_6171c', 'value': 'ABANDON',
                    'varType': 'string', 'variable_selector': ['6170c', 'text']}],
})
# 6171d (contains [6170d, text])
insert_before_default(find_node('6171d')['data']['cases'], {
    'case_id': 'abandon', 'logical_operator': 'and',
    'conditions': [{'comparison_operator': 'contains', 'id': 'c_ab_6171d', 'value': 'ABANDON',
                    'varType': 'string', 'variable_selector': ['6170d', 'text']}],
})

# ==================== 4. 新增 6162-abort (reset IDLE, mirror 6162) + 6162-out (话术) ====================
RESET_ITEMS = [
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6901', 'str_idle'], 'variable_selector': ['conversation', 'cv_flow_state']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6901', 'str_empty'], 'variable_selector': ['conversation', 'cv_feedback_zh']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6901', 'str_empty'], 'variable_selector': ['conversation', 'cv_record_id']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6901', 'str_empty'], 'variable_selector': ['conversation', 'cv_mokuai']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6901', 'str_empty'], 'variable_selector': ['conversation', 'cv_huanjing']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6901', 'str_empty'], 'variable_selector': ['conversation', 'cv_leixing']},
]
nodes.append(assigner('6162-abort', 'var_放弃结束reset IDLE', RESET_ITEMS, 300, 760))

CODE_6162OUT = (
    'def main() -> dict:\n'
    '    text = "好的,本次反馈就到这里啦。若还有其他问题,随时联系我为您处理哦~"\n'
    '    return {"answer_text": text + "\\n<!--SYS:TIMER|action=cancel-->"}\n'
)
nodes.append(code('6162-out', '放弃结束话术', CODE_6162OUT, {'answer_text': out_str()}, [], 300, 880))

# ==================== 5. 加边 ====================
NEW_EDGES = [
    edge('e-6171-abort', '6171', '6162-abort', 'abandon', 'if-else', 'variable-assigner'),
    edge('e-6171b-abort', '6171b', '6162-abort', 'abandon', 'if-else', 'variable-assigner'),
    edge('e-6171c-abort-ab', '6171c', '6162-abort', 'abandon', 'if-else', 'variable-assigner'),
    edge('e-6171c-abort-dm', '6171c', '6162-abort', 'deny_modify', 'if-else', 'variable-assigner'),
    edge('e-6171d-abort', '6171d', '6162-abort', 'abandon', 'if-else', 'variable-assigner'),
    edge('e-6162abort-6162out', '6162-abort', '6162-out', 'source', 'variable-assigner', 'code'),
    edge('e-6162out-6098', '6162-out', '6098', 'source', 'code', 'answer'),
]
for e in NEW_EDGES:
    edges.append(e)

# ==================== 6. 6098 加 [6162-out, answer_text] ====================
n6098 = find_node('6098')
n6098['data']['variables'].append(['6162-out', 'answer_text'])

# ==================== dump ====================
with open(V23, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
ids = [n['id'] for n in nodes]
assert len(ids) == len(set(ids)), 'duplicate node id'
idset = set(ids)
for e in edges:
    assert e['source'] in idset and e['target'] in idset, 'dangling edge: ' + e['id']
# 每个 if-else 的 abandon/deny_modify case 有出边
for src, handle in [('6171', 'abandon'), ('6171b', 'abandon'), ('6171c', 'abandon'),
                    ('6171c', 'deny_modify'), ('6171d', 'abandon')]:
    assert any(e['source'] == src and e['sourceHandle'] == handle for e in edges), f'no edge {src}[{handle}]'
# 6162-abort/6162-out 存在且有出边
assert any(e['source'] == '6162-abort' for e in edges)
assert any(e['source'] == '6162-out' and e['target'] == '6098' for e in edges)
# 6098 含 6162-out
assert ['6162-out', 'answer_text'] in n6098['data']['variables']
# default→6162→6003 re-entry 保留 (4 条 default 边 + 6162→6003 边仍在)
for src in ['6171', '6171b', '6171c', '6171d']:
    assert any(e['source'] == src and e['sourceHandle'] == 'default' and e['target'] == '6162' for e in edges), f'{src} default→6162 lost'
assert any(e['source'] == '6162' and e['target'] == '6003' for e in edges), '6162→6003 re-entry lost'
# 6901 仍不变 (无 feishu_base_url)
assert 'feishu_base_url' not in find_node('6901')['data']['outputs']

print('v23 generated:', V23)
print('nodes:', len(nodes), 'edges:', len(edges))
print('6170-parse has ABANDON:', 'ABANDON' in find_node('6170-parse')['data']['code'])
for nid in ['6170', '6170b', '6170c', '6170d']:
    print(nid, 'has ABANDON prompt:', 'ABANDON' in find_node(nid)['data']['prompt_template'][0]['text'])
for nid in ['6171', '6171b', '6171c', '6171d']:
    cases = [c['case_id'] for c in find_node(nid)['data']['cases']]
    print(nid, 'cases:', cases)
