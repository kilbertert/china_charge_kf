#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次二.3 patch: 从 v18.yml 生成 v19.yml (修改窗: 保活期内 LLM 判断 修改/新增)

根因: 写主表后 6261 立刻回 IDLE, 用户"我记错了改模块"时 IDLE→6240查表(新模块)
      查不到旧记录→6241判不存在→走新增, 于是飞书新增第二条而非覆盖.

方案: 写主表/写update后 不回IDLE, 改设 await_modify_window 态 (保留 cv_record_id
      + cv_row_summary=刚记录内容). 下次输入 6601 命中 await_modify_window →
      6239-llm 判断 MODIFY/NEW/OTHER:
        MODIFY → 转写新消息 → 设 cv_feedback_zh + await_diff_decision → 6173 对比询问
                 → 6175 汇报 → 6176 update 覆盖原记录
        NEW/OTHER → 设 IDLE → 走原 IDLE 流程 (6240 查表新增 / 6201 判非bug)

改: 6901 加常量 str_await_modify_window / 6601 加 case / 6261+6176c 改设态+cv_row_summary
加: 6 新节点 (6239-llm/6239-if/6239-trans/6239-trans-parse/6239-modify-assigner/6239-new-idle)
"""
from ruamel.yaml import YAML

V18 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v18.yml'
V19 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v19.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V18) as f:
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


def llm(nid, title, sys_id, sys_text, user_id, user_text, x, y, vision=False):
    return {
        'data': {
            'model': {'mode': 'chat', 'name': 'Doubao-Seed-2.0-lite',
                      'provider': 'langgenius/volcengine_maas/volcengine_maas'},
            'prompt_template': [
                {'id': sys_id, 'role': 'system', 'text': sys_text},
                {'id': user_id, 'role': 'user', 'text': user_text},
            ],
            'context': {'enabled': False, 'variable_selector': []},
            'vision': {'configs': {'detail': 'high', 'variable_selector': ['sys', 'files']}, 'enabled': vision},
            'reasoning_format': 'separated',
            'selected': False,
            'title': title,
            'type': 'llm',
        },
        'height': 88, 'id': nid,
        'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def code(nid, title, code_str, outputs, variables, x, y):
    return {
        'data': {
            'code': code_str, 'code_language': 'python3',
            'outputs': outputs, 'selected': False, 'title': title,
            'type': 'code', 'variables': variables,
        },
        'height': 88, 'id': nid,
        'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def assigner(nid, title, items, x, y):
    return {
        'data': {'items': items, 'selected': False, 'title': title, 'type': 'assigner', 'version': '2'},
        'height': 88, 'id': nid,
        'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def ifelse(nid, title, cases, x, y):
    return {
        'data': {'cases': cases, 'selected': False, 'title': title, 'type': 'if-else'},
        'height': 118, 'id': nid,
        'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def edge(eid, src, tgt, sh, st, tt, th='target'):
    return {'data': {'sourceType': st, 'targetType': tt}, 'id': eid, 'source': src,
            'sourceHandle': sh, 'target': tgt, 'targetHandle': th, 'type': 'custom'}


def out_str():
    return {'children': None, 'type': 'string'}


# ==================== 1. 6901 加常量 str_await_modify_window ====================
n6901 = find_node('6901')
n6901['data']['code'] = n6901['data']['code'].replace(
    '"str_await_confirm_modify": "await_confirm_modify"',
    '"str_await_confirm_modify": "await_confirm_modify",\n'
    '        "str_await_modify_window": "await_modify_window"'
)
n6901['data']['outputs']['str_await_modify_window'] = out_str()

# ==================== 2. 6601 加 case await_modify_window (default 之前) ====================
n6601 = find_node('6601')
cases = n6601['data']['cases']
amw_case = {
    'case_id': 'await_modify_window', 'logical_operator': 'and',
    'conditions': [{'comparison_operator': 'contains', 'id': 'cond_6601_amw',
                    'value': 'await_modify_window', 'varType': 'string',
                    'variable_selector': ['conversation', 'cv_flow_state']}]
}
default_idx = next(i for i, c in enumerate(cases) if c['case_id'] == 'default')
cases.insert(default_idx, amw_case)

# ==================== 3. 6261 改: cv_flow_state→await_modify_window + 加 cv_row_summary ====================
n6261 = find_node('6261')
for item in n6261['data']['items']:
    if item.get('variable_selector') == ['conversation', 'cv_flow_state']:
        item['value'] = ['6901', 'str_await_modify_window']
n6261['data']['items'].append({
    'input_type': 'variable', 'operation': 'over-write',
    'value': ['conversation', 'cv_feedback_zh'],
    'variable_selector': ['conversation', 'cv_row_summary']
})

# ==================== 4. 6176c 改: 同上 (update 后也进修改窗) ====================
n6176c = find_node('6176c')
for item in n6176c['data']['items']:
    if item.get('variable_selector') == ['conversation', 'cv_flow_state']:
        item['value'] = ['6901', 'str_await_modify_window']
n6176c['data']['items'].append({
    'input_type': 'variable', 'operation': 'over-write',
    'value': ['conversation', 'cv_feedback_zh'],
    'variable_selector': ['conversation', 'cv_row_summary']
})

# ==================== 5. 新节点 (6 个) ====================

# --- 6239-llm 修改窗意图判断 ---
P_6239LLM = (
    '你是充电桩客服对话意图判定器。用户刚刚成功记录了一条bug反馈'
    '(记录编号 {{#conversation.cv_record_id#}}),记录内容摘要: {{#conversation.cv_row_summary#}}。\n\n'
    '现在用户又发来一条消息,请判断用户意图,只输出一个标签,不要任何其他文字:\n'
    '- MODIFY : 用户要修改/更正刚才记录的那条反馈(如"记错了""不对""应该是""改成""我说错了")\n'
    '- NEW    : 用户在反馈一个全新的、与刚才记录无关的问题\n'
    '- OTHER  : 闲聊、问候、或与bug反馈无关的内容\n\n'
    '用户消息: {{#6002.query_text#}}'
)
nodes.append(llm('6239-llm', '修改窗意图判断', 'm6239-sys', P_6239LLM,
                 'm6239-user', '{{#6002.query_text#}}', -220, 700))

# --- 6239-if 修改窗分发 ---
nodes.append(ifelse('6239-if', '修改窗分发', [
    {'case_id': 'modify', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_m_6239', 'value': 'MODIFY',
                     'varType': 'string', 'variable_selector': ['6239-llm', 'text']}]},
    {'case_id': 'new', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_n_6239', 'value': 'NEW',
                     'varType': 'string', 'variable_selector': ['6239-llm', 'text']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_6239_default',
                     'varType': 'string', 'variable_selector': ['6002', 'query_text']}]},
], 220, 700))

# --- 6239-trans 转写 (复用 6177 prompt) ---
P_6239TRANS = ('你是 B 端 SaaS 产品客户反馈转写引擎。将用户反馈转为结构化数据。\n\n'
               '【输入】用户反馈: {{#6002.query_text#}}\n\n'
               '严格输出 JSON,仅含 mokuai/caozuomiaoshu/huanjing/leixing 四个字段,无额外说明:\n'
               '{\n'
               '  "mokuai": "模块标准名称(15字以内,无法识别填待确认)",\n'
               '  "caozuomiaoshu": "标准化操作路径与问题现象描述(80字以内)",\n'
               '  "huanjing": "后台/管家端/用户端(无法判定填待确认)",\n'
               '  "leixing": "bug/优化(无法判定填待确认)"\n'
               '}')
nodes.append(llm('6239-trans', '修改窗转写', 'm6239t-sys', P_6239TRANS,
                 'm6239t-user', '{{#6002.query_text#}}', 480, 700))

# --- 6239-trans-parse 解析 (复用 6177-parse code) ---
CODE_6239PARSE = ('def main(llm_text: str) -> dict:\n'
                  '    import json, re\n'
                  '    text = llm_text or ""\n'
                  '    m = re.search(r"\\{[^{}]*\\}", text)\n'
                  '    if not m:\n'
                  '        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}\n'
                  '    try:\n'
                  '        obj = json.loads(m.group(0))\n'
                  '        return {\n'
                  '            "mokuai": str(obj.get("mokuai","")).strip()[:50],\n'
                  '            "caozuomiaoshu": str(obj.get("caozuomiaoshu","")).strip()[:500],\n'
                  '            "huanjing": str(obj.get("huanjing","")).strip()[:20],\n'
                  '            "leixing": str(obj.get("leixing","")).strip()[:20]\n'
                  '        }\n'
                  '    except Exception:\n'
                  '        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}\n')
nodes.append(code('6239-trans-parse', '修改窗转写解析', CODE_6239PARSE,
                  {'mokuai': out_str(), 'caozuomiaoshu': out_str(), 'huanjing': out_str(), 'leixing': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6239-trans', 'text']}], 740, 700))

# --- 6239-modify-assigner 设 cv_feedback_zh/mokuai/huanjing/leixing + await_diff_decision ---
nodes.append(assigner('6239-modify-assigner', '修改窗设cv+await_diff_decision', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6239-trans-parse', 'caozuomiaoshu'],
     'variable_selector': ['conversation', 'cv_feedback_zh']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6239-trans-parse', 'mokuai'],
     'variable_selector': ['conversation', 'cv_mokuai']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6239-trans-parse', 'huanjing'],
     'variable_selector': ['conversation', 'cv_huanjing']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6239-trans-parse', 'leixing'],
     'variable_selector': ['conversation', 'cv_leixing']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_await_diff_decision'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 1000, 700))

# --- 6239-new-idle 回 IDLE ---
nodes.append(assigner('6239-new-idle', '修改窗回IDLE', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_idle'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 220, 820))

# ==================== 6. 新边 ====================
NEW_EDGES = [
    # 6601 → 6239-llm (await_modify_window)
    edge('e-6601-amw-6239llm', '6601', '6239-llm', 'await_modify_window', 'if-else', 'llm'),
    # 6239-llm → 6239-if
    edge('e-6239llm-6239if', '6239-llm', '6239-if', 'source', 'llm', 'if-else'),
    # 6239-if 三分支
    edge('e-6239if-modify-6239trans', '6239-if', '6239-trans', 'modify', 'if-else', 'llm'),
    edge('e-6239if-new-6239idle', '6239-if', '6239-new-idle', 'new', 'if-else', 'variable-assigner'),
    edge('e-6239if-default-6239idle', '6239-if', '6239-new-idle', 'default', 'if-else', 'variable-assigner'),
    # MODIFY 链
    edge('e-6239trans-6239parse', '6239-trans', '6239-trans-parse', 'source', 'llm', 'code'),
    edge('e-6239parse-6239assigner', '6239-trans-parse', '6239-modify-assigner', 'source', 'code', 'variable-assigner'),
    edge('e-6239assigner-6173', '6239-modify-assigner', '6173', 'source', 'variable-assigner', 'llm'),
    # NEW/OTHER 回 IDLE 走原流程
    edge('e-6239idle-6003', '6239-new-idle', '6003', 'source', 'variable-assigner', 'if-else'),
]
for e in NEW_EDGES:
    edges.append(e)

# ==================== 7. 6176a 改: update 同步「模块/功能点」「类型」(用户改模块时飞书模块字段同步) ====================
n6176a = find_node('6176a')
n6176a['data']['code'] = (
    'def main(record_id: str, feedback_zh: str, mokuai: str, leixing: str) -> dict:\n'
    '    import json\n'
    '    fields = {}\n'
    '    if mokuai:\n'
    '        fields["模块/功能点"] = mokuai[:100]\n'
    '    if feedback_zh:\n'
    '        fields["操作描述"] = ((mokuai + " ") if mokuai else "") + feedback_zh[:2000]\n'
    '        fields["产品备注"] = feedback_zh[:500]\n'
    '    fields["类型"] = (leixing or "bug")[:10]\n'
    '    return {"body_json": json.dumps({"record_id": record_id, "fields": fields}, ensure_ascii=False)}\n'
)
n6176a['data']['variables'] = [
    {'variable': 'record_id', 'value_selector': ['conversation', 'cv_record_id']},
    {'variable': 'feedback_zh', 'value_selector': ['conversation', 'cv_feedback_zh']},
    {'variable': 'mokuai', 'value_selector': ['conversation', 'cv_mokuai']},
    {'variable': 'leixing', 'value_selector': ['conversation', 'cv_leixing']},
]

# ==================== dump ====================
with open(V19, 'w') as f:
    yaml.dump(data, f)

print('v19 generated:', V19)
print('nodes:', len(nodes), 'edges:', len(edges))
