#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""缺口2+6 patch: 从 v23.yml 生成 v24.yml

Gap6 (Q4 无差异 → 结束话术):
  - 6170c prompt 加 NO_DIFF 标签(内容一致/记录准确,无需修改)
  - 6171c 加 no_diff case → 6162-abort(复用 Gap5 结束话术路径)

Gap2 (客户否认 → 重新查表,而非直接转新增):
  现状: 6171b[deny_identity]→6177→6177-parse→6177-assigner→6244(确认新增, 直接当新反馈)
  改: 6177-assigner→6240builddnl→6240-denial→6240-denial-parse→6241-denial
      命中→6242b-denial(设cv+await_confirm_identity)→6242-denial(D4模板+TIMER)→6098
      未命中→6244(确认新增, cv已由6177-assigner设好)
  为什么独立链: 6240/6240-parse/6241/6242/6242b 互引固定 selector, 复用会断引用;
              6241[default]→6250-if→6243 读[6250-judge](denial 未跑会覆盖cv空)。
  6177-assigner 已设 cv_mokuai/huanjing/leixing/feedback_zh+await_confirm_new, 故 MISS→6244 读 cv 可用。
"""
import copy
from ruamel.yaml import YAML

V23 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v23.yml'
V24 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v24.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V23) as f:
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


def code_node(nid, title, code_str, outputs, variables, x, y):
    return {
        'data': {'code': code_str, 'code_language': 'python3', 'outputs': outputs,
                 'selected': False, 'title': title, 'type': 'code', 'variables': variables},
        'height': 88, 'id': nid, 'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def assigner_node(nid, title, items, x, y):
    return {
        'data': {'items': items, 'selected': False, 'title': title, 'type': 'assigner', 'version': '2'},
        'height': 88, 'id': nid, 'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def ifelse_node(nid, title, cases, x, y):
    return {
        'data': {'cases': cases, 'selected': False, 'title': title, 'type': 'if-else'},
        'height': 118, 'id': nid, 'position': pos(x, y), 'positionAbsolute': pos(x, y),
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


# ============================================================
# Gap6: 6170c 加 NO_DIFF 标签 + 6171c 加 no_diff case
# ============================================================
NO_DIFF_LINE = '- NO_DIFF          : 用户表示内容一致/记录准确,无需修改(没差异/一样/内容对的/一致)'
n6170c = find_node('6170c')
txt = n6170c['data']['prompt_template'][0]['text']
assert '- IRRELEVANT' in txt, '6170c IRRELEVANT anchor missing'
n6170c['data']['prompt_template'][0]['text'] = txt.replace(
    '- IRRELEVANT', NO_DIFF_LINE + '\n- IRRELEVANT', 1)

insert_before_default(find_node('6171c')['data']['cases'], {
    'case_id': 'no_diff', 'logical_operator': 'and',
    'conditions': [{'comparison_operator': 'contains', 'id': 'c_nd_6171c', 'value': 'NO_DIFF',
                    'varType': 'string', 'variable_selector': ['6170c', 'text']}],
})
edges.append(edge('e-6171c-nodiff-abort', '6171c', '6162-abort', 'no_diff', 'if-else', 'variable-assigner'))

# ============================================================
# Gap2: 否认重查独立链 (6 新节点)
# ============================================================
# 1. 6240builddnl (code): body_json from [6177-parse, mokuai]
CODE_BUILD_DENIAL = (
    'def main(mokuai: str) -> dict:\n'
    '    import json\n'
    '    return {"body_json": json.dumps({"keyword": mokuai or "", "limit": 5}, ensure_ascii=False)}\n'
)
nodes.append(code_node('6240builddnl', 'D2组装查表body(否认)', CODE_BUILD_DENIAL,
                       {'body_json': out_str()},
                       [{'variable': 'mokuai', 'value_selector': ['6177-parse', 'mokuai']}],
                       1000, 380))

# 2. 6240-denial (HTTP): 深拷贝 6240, body 改读 6240builddnl
#    注意: body 模板 {{#nodeId.var#}} 不支持连字符 nodeId(正则\w+不匹配-),
#    故 build 节点用无连字符 id 6240builddnl; 6240-denial 等经 value_selector 引用,连字符 OK
n6240 = find_node('6240')
http_data = copy.deepcopy(n6240['data'])
http_data['body']['data'][0]['value'] = '{{#6240builddnl.body_json#}}'
http_data['title'] = 'D2 查询问题追踪表(否认重查)'
nodes.append({
    'data': http_data, 'height': 200, 'id': '6240-denial',
    'position': pos(1240, 380), 'positionAbsolute': pos(1240, 380),
    'selected': False, 'type': 'custom', 'width': 242,
})

# 3. 6240-denial-parse (code): 同 6240-parse, 读 [6240-denial, body]
CODE_PARSE_DENIAL = (
    'def main(http_body: str) -> dict:\n'
    '    import json\n'
    '    try:\n'
    '        data = json.loads(http_body or "{}")\n'
    '    except Exception:\n'
    '        return {"hit_record_id": "", "row_summary": ""}\n'
    '    hits = data.get("hits") or []\n'
    '    if not hits:\n'
    '        return {"hit_record_id": "", "row_summary": ""}\n'
    '    h = hits[0]\n'
    '    rid = h.get("record_id", "")\n'
    '    op = h.get("op_desc", "") or h.get("summary", "")\n'
    '    return {"hit_record_id": rid, "row_summary": op[:500]}\n'
)
nodes.append(code_node('6240-denial-parse', 'D2解析查表(否认)', CODE_PARSE_DENIAL,
                       {'hit_record_id': out_str(), 'row_summary': out_str()},
                       [{'variable': 'http_body', 'value_selector': ['6240-denial', 'body']}],
                       1480, 380))

# 4. 6241-denial (if-else): bug_exist/default on [6240-denial-parse, hit_record_id]
nodes.append(ifelse_node('6241-denial', 'D2是否已存在(否认)', [
    {'case_id': 'bug_exist', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_den_be', 'varType': 'string',
                     'variable_selector': ['6240-denial-parse', 'hit_record_id']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_den_def', 'varType': 'string',
                     'variable_selector': ['6002', 'query_text']}]},
], 1720, 380))

# 5. 6242b-denial (assigner): 设 cv_record_id/cv_row_summary/await_confirm_identity from 6240-denial-parse
nodes.append(assigner_node('6242b-denial', 'var_否认命中设身份态', [
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6240-denial-parse', 'hit_record_id'],
     'variable_selector': ['conversation', 'cv_record_id']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6240-denial-parse', 'row_summary'],
     'variable_selector': ['conversation', 'cv_row_summary']},
    {'input_type': 'variable', 'operation': 'over-write', 'value': ['6901', 'str_await_confirm_identity'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 1960, 380))

# 6. 6242-denial (code): D4 模板 + TIMER (合并 6242+6242c), 读 [6240-denial-parse, row_summary]
CODE_D4_DENIAL = (
    'def main(row_summary: str) -> dict:\n'
    '    s = (row_summary or "").strip()\n'
    '    if not s:\n'
    '        s = "该记录内容"\n'
    '    text = "我们查询到已有相关追踪记录:\\n" + s + "\\n\\n请问这是您反馈的问题吗？"\n'
    '    return {"answer_text": text + "\\n<!--SYS:TIMER|action=arm|state=await_confirm_identity-->"}\n'
)
nodes.append(code_node('6242-denial', 'D4 命中汇报(否认)', CODE_D4_DENIAL,
                       {'answer_text': out_str()},
                       [{'variable': 'row_summary', 'value_selector': ['6240-denial-parse', 'row_summary']}],
                       2200, 380))

# ---- Gap2 边改动 ----
# 删 6177-assigner→6244 (改为→6240builddnl)
edges[:] = [e for e in edges if not (e['source'] == '6177-assigner' and e['target'] == '6244')]
# 加 denial 链边
for e in [
    edge('e-6177a-6240builddnl', '6177-assigner', '6240builddnl', 'source', 'variable-assigner', 'code'),
    edge('e-6240builddnl-6240-d', '6240builddnl', '6240-denial', 'source', 'code', 'http-request'),
    edge('e-6240-d-6240parse-d', '6240-denial', '6240-denial-parse', 'source', 'http-request', 'code'),
    edge('e-6240parse-d-6241-d', '6240-denial-parse', '6241-denial', 'source', 'code', 'if-else'),
    edge('e-6241-d-be-6242b-d', '6241-denial', '6242b-denial', 'bug_exist', 'if-else', 'variable-assigner'),
    edge('e-6242b-d-6242-d', '6242b-denial', '6242-denial', 'source', 'variable-assigner', 'code'),
    edge('e-6242-d-6098', '6242-denial', '6098', 'source', 'code', 'answer'),
    edge('e-6241-d-def-6244', '6241-denial', '6244', 'default', 'if-else', 'llm'),
]:
    edges.append(e)

# 6098 加 [6242-denial, answer_text]
find_node('6098')['data']['variables'].append(['6242-denial', 'answer_text'])

# ============================================================
# dump
# ============================================================
with open(V24, 'w') as f:
    yaml.dump(data, f)

# ============================================================
# 校验
# ============================================================
import ast
ids = [n['id'] for n in nodes]
assert len(ids) == len(set(ids)), 'duplicate node id'
idset = set(ids)
for e in edges:
    assert e['source'] in idset and e['target'] in idset, 'dangling edge: ' + e['id']
# Gap6
assert 'NO_DIFF' in find_node('6170c')['data']['prompt_template'][0]['text']
assert any(e['source'] == '6171c' and e['sourceHandle'] == 'no_diff' and e['target'] == '6162-abort' for e in edges)
# Gap2 新节点存在
for nid in ['6240builddnl', '6240-denial', '6240-denial-parse', '6241-denial', '6242b-denial', '6242-denial']:
    assert nid in idset, nid + ' missing'
# 6177-assigner→6244 已删, 改→6240builddnl
assert not any(e['source'] == '6177-assigner' and e['target'] == '6244' for e in edges)
assert any(e['source'] == '6177-assigner' and e['target'] == '6240builddnl' for e in edges)
# 6241-denial 两个 case 都有出边
assert any(e['source'] == '6241-denial' and e['sourceHandle'] == 'bug_exist' for e in edges)
assert any(e['source'] == '6241-denial' and e['sourceHandle'] == 'default' and e['target'] == '6244' for e in edges)
# 6242-denial 在 6098
assert ['6242-denial', 'answer_text'] in find_node('6098')['data']['variables']
# 6240-denial HTTP body 读 6240builddnl
assert '6240builddnl.body_json' in find_node('6240-denial')['data']['body']['data'][0]['value']
# 原始链路保留: 6171b[deny_identity]→6177, 6177→6177-parse→6177-assigner, 6243→6244
assert any(e['source'] == '6171b' and e['sourceHandle'] == 'deny_identity' and e['target'] == '6177' for e in edges)
assert any(e['source'] == '6243' and e['target'] == '6244' for e in edges)

print('v24 generated:', V24)
print('nodes:', len(nodes), 'edges:', len(edges))
print('Gap6: 6170c NO_DIFF:', 'NO_DIFF' in find_node('6170c')['data']['prompt_template'][0]['text'])
print('Gap6: 6171c cases:', [c['case_id'] for c in find_node('6171c')['data']['cases']])
print('Gap2: 6177-assigner→6244 removed:', not any(e['source'] == '6177-assigner' and e['target'] == '6244' for e in edges))
print('Gap2: denial chain nodes present')
