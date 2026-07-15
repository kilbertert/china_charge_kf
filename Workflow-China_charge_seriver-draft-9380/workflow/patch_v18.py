#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次二.2 patch: 从 v17.yml 生成 v18.yml (命中分支多轮闭环)
改: 6901加3常量 / 6242 prompt+出边 / 6601 cases+出边
加: 21 新节点 + 新边
"""
from ruamel.yaml import YAML

V17 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v17.yml'
V18 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v18.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V17) as f:
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


def http(nid, title, url, body_ref, x, y):
    return {
        'data': {
            'authorization': {'config': None, 'type': 'no-auth'},
            'body': {'data': [{'type': 'text', 'value': body_ref}], 'type': 'json'},
            'error_strategy': 'fail-branch',
            'headers': 'Content-Type:application/json\n\nAuthorization:Bearer rTlcyp8ezVWupzXmGrfPh-l_BQxEQaEqCHCtJbyxs6E',
            'method': 'POST', 'params': '',
            'retry_config': {'max_retries': 3, 'retry_enabled': True, 'retry_interval': 100},
            'ssl_verify': True,
            'timeout': {'max_connect_timeout': 10, 'max_read_timeout': 30, 'max_write_timeout': 30},
            'selected': False, 'title': title, 'type': 'http-request', 'url': url,
        },
        'height': 200, 'id': nid,
        'position': pos(x, y), 'positionAbsolute': pos(x, y),
        'selected': False, 'type': 'custom', 'width': 242,
    }


def edge(eid, src, tgt, sh, st, tt, th='target'):
    return {'data': {'sourceType': st, 'targetType': tt}, 'id': eid, 'source': src,
            'sourceHandle': sh, 'target': tgt, 'targetHandle': th, 'type': 'custom'}


def out_str():
    return {'children': None, 'type': 'string'}


# ==================== 1. 改 6901 加 3 常量 ====================
n6901 = find_node('6901')
c = n6901['data']['code']
c = c.replace(
    '"str_idle": "IDLE"',
    '"str_idle": "IDLE",\n        "str_await_confirm_identity": "await_confirm_identity",'
    '\n        "str_await_diff_decision": "await_diff_decision",'
    '\n        "str_await_confirm_modify": "await_confirm_modify"'
)
n6901['data']['code'] = c
for k in ('str_await_confirm_identity', 'str_await_diff_decision', 'str_await_confirm_modify'):
    n6901['data']['outputs'][k] = out_str()

# ==================== 2. 改 6242 prompt ====================
n6242 = find_node('6242')
n6242['data']['prompt_template'][0]['text'] = (
    '你是充电桩智能客服。用户反馈的问题在追踪表中命中了一条已有记录。汇报该记录内容,并引导用户确认。\n\n'
    '**规则**:\n\n1. 严格只输出最终答案文本\n\n'
    '2. 简述命中记录的内容(基于检索结果)\n\n'
    '3. 询问"这是您反馈的问题吗?"\n\n4. 简洁,100字以内\n\n'
    '用户问: {{#6002.query_text#}}\n\n命中的问题追踪记录:\n\n{{#context#}}'
)

# ==================== 3. 改 6242 出边: 6242→6098 改 6242→6242b ====================
for e in edges:
    if e['id'] == 'e-6242-6098':
        e['target'] = '6242b'
        e['id'] = 'e-6242-6242b'
        e['data']['targetType'] = 'variable-assigner'

# ==================== 4. 改 6601 cases + 出边 ====================
n6601 = find_node('6601')
n6601['data']['cases'] = [
    {'case_id': 'await_confirm_new', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'cond_6601_acn',
                     'value': 'await_confirm_new', 'varType': 'string',
                     'variable_selector': ['conversation', 'cv_flow_state']}]},
    {'case_id': 'await_confirm_identity', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'cond_6601_aci',
                     'value': 'await_confirm_identity', 'varType': 'string',
                     'variable_selector': ['conversation', 'cv_flow_state']}]},
    {'case_id': 'await_diff_decision', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'cond_6601_add',
                     'value': 'await_diff_decision', 'varType': 'string',
                     'variable_selector': ['conversation', 'cv_flow_state']}]},
    {'case_id': 'await_confirm_modify', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'cond_6601_acm',
                     'value': 'await_confirm_modify', 'varType': 'string',
                     'variable_selector': ['conversation', 'cv_flow_state']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_6601_default',
                     'varType': 'string', 'variable_selector': ['6002', 'query_text']}]},
]
# 删 e-6601-idle-6003
edges[:] = [e for e in edges if e['id'] != 'e-6601-idle-6003']
# 改 e-6601-default-6170 → e-6601-await_confirm_new-6170
for e in edges:
    if e['id'] == 'e-6601-default-6170':
        e['sourceHandle'] = 'await_confirm_new'
        e['id'] = 'e-6601-await_confirm_new-6170'

# ==================== 4.5 修 6240 查表:body 变量在 JSON 字符串里不替换(Dify bug) ====================
# v17 6240 body value='{"keyword": "{{#...#}}"}' 字面未替换(process_data.request 确认)。
# 改用 code 组装 body_json,HTTP body 整体引用(同 6260b/6176b 模式)。keyword 用 mokuai(模块名稳定)。
n6240 = find_node('6240')
for item in n6240['data']['body']['data']:
    if item.get('type') == 'text':
        item['value'] = '{{#6240build.body_json#}}'
# 删原边 6250-parse→6240,改为 6250-parse→6240build→6240
edges[:] = [e for e in edges if e['id'] != 'e-6250-parse-6240']

# 6260a 写表 op_desc 前置 mokuai,使"操作描述"含模块名,6240 contains mokuai 可命中
n6260a = find_node('6260a')
n6260a['data']['code'] = n6260a['data']['code'].replace(
    'fields["操作描述"] = caozuomiaoshu[:2000]',
    'fields["操作描述"] = ((mokuai + " ") if mokuai else "") + caozuomiaoshu[:2000]'
)

# 6098 answer 聚合:补 v18 新分支末尾(否则汇聚输出空)
n6098 = find_node('6098')
for nid in ['6242c', '6173-timer', '6175-timer', '6176d']:
    n6098['data']['variables'].append([nid, 'answer_text'])

# ==================== 5. 新节点(21 个) ====================

# --- 命中首轮 ---
nodes.append(assigner('6242b', 'var_标记命中待确认身份', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6240-parse', 'hit_record_id'],
     'variable_selector': ['conversation', 'cv_record_id']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6240-parse', 'row_summary'],
     'variable_selector': ['conversation', 'cv_row_summary']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_await_confirm_identity'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 1960, 820))

CODE_6242C = ('def main(llm_text: str) -> dict:\n'
              '    marker = "<!--SYS:TIMER|action=arm|state=await_confirm_identity-->"\n'
              '    return {"answer_text": (llm_text or "") + "\\n" + marker}\n')
nodes.append(code('6242c', '命中拼TIMER标记', CODE_6242C,
                  {'answer_text': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6242', 'text']}], 2200, 820))

# 6240build: 组装查表 body_json(keyword=mokuai),解决 HTTP body 变量不替换
CODE_6240BUILD = ('def main(mokuai: str) -> dict:\n'
                  '    import json\n'
                  '    return {"body_json": json.dumps({"keyword": mokuai or "", "limit": 5}, ensure_ascii=False)}\n')
nodes.append(code('6240build', 'D2组装查表body', CODE_6240BUILD,
                  {'body_json': out_str()},
                  [{'variable': 'mokuai', 'value_selector': ['6250-parse', 'mokuai']}], 1380, 620))

# --- N17b 身份确认 ---
P_6170B = ('你是客服对话相关性判定器。当前待确认态: await_confirm_identity'
           '(我们告知用户命中了已有问题记录,在问"这是您反馈的问题吗")。\n\n'
           '【命中旧行内容】: {{#conversation.cv_row_summary#}}\n'
           '【用户已转写反馈】: {{#conversation.cv_feedback_zh#}}\n'
           '【用户新消息】: {{#6002.query_text#}}\n\n'
           '只输出一个标签,不要任何其他文字:\n'
           '- CONFIRM_IDENTITY : 用户确认是自己的问题(是/对/是我的)\n'
           '- DENY_IDENTITY    : 用户否认(不是/不对/不是我的)\n'
           '- MODIFY_EXISTING  : 用户要求修改这条已有记录\n'
           '- IRRELEVANT       : 开新话题/无关')
nodes.append(llm('6170b', 'N17b 身份确认分类', 'n17b-sys', P_6170B,
                 'n17b-user', '{{#6002.query_text#}}', -220, 340))
nodes.append(ifelse('6171b', 'N17b 分发', [
    {'case_id': 'confirm_identity', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_ci_b', 'value': 'CONFIRM_IDENTITY',
                     'varType': 'string', 'variable_selector': ['6170b', 'text']}]},
    {'case_id': 'modify_existing', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_me_b', 'value': 'MODIFY_EXISTING',
                     'varType': 'string', 'variable_selector': ['6170b', 'text']}]},
    {'case_id': 'deny_identity', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_di_b', 'value': 'DENY_IDENTITY',
                     'varType': 'string', 'variable_selector': ['6170b', 'text']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_6171b_default',
                     'varType': 'string', 'variable_selector': ['6002', 'query_text']}]},
], 220, 340))

# --- N17c 修改决策 ---
P_6170C = ('你是客服对话相关性判定器。当前待确认态: await_diff_decision'
           '(我们问了用户"是否要修改这条已有记录")。\n\n'
           '【已有记录】: {{#conversation.cv_row_summary#}}\n'
           '【用户反馈】: {{#conversation.cv_feedback_zh#}}\n'
           '【用户新消息】: {{#6002.query_text#}}\n\n'
           '只输出一个标签,不要任何其他文字:\n'
           '- CONFIRM_MODIFY   : 用户确认要修改(是/改/修改/要改)\n'
           '- DENY_MODIFY      : 用户不改了(不用/算了/不改/不用改)\n'
           '- MODIFY_EXISTING  : 用户补充新的修改要求\n'
           '- IRRELEVANT       : 开新话题/无关')
nodes.append(llm('6170c', 'N17c 修改决策分类', 'n17c-sys', P_6170C,
                 'n17c-user', '{{#6002.query_text#}}', -220, 460))
nodes.append(ifelse('6171c', 'N17c 分发', [
    {'case_id': 'confirm_modify', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_cm_c', 'value': 'CONFIRM_MODIFY',
                     'varType': 'string', 'variable_selector': ['6170c', 'text']}]},
    {'case_id': 'modify_existing', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_me_c', 'value': 'MODIFY_EXISTING',
                     'varType': 'string', 'variable_selector': ['6170c', 'text']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_6171c_default',
                     'varType': 'string', 'variable_selector': ['6002', 'query_text']}]},
], 220, 460))

# --- N17d 修改完成确认 ---
P_6170D = ('你是客服对话相关性判定器。当前待确认态: await_confirm_modify'
           '(我们汇报了修改后的内容,在问"确认无误吗")。\n\n'
           '【已有记录】: {{#conversation.cv_row_summary#}}\n'
           '【修改后反馈】: {{#conversation.cv_feedback_zh#}}\n'
           '【用户新消息】: {{#6002.query_text#}}\n\n'
           '只输出一个标签,不要任何其他文字:\n'
           '- CONFIRM_DONE     : 用户确认无误(确认/对/没问题/可以)\n'
           '- MODIFY_EXISTING  : 用户还要改\n'
           '- IRRELEVANT       : 开新话题/无关')
nodes.append(llm('6170d', 'N17d 修改完成确认分类', 'n17d-sys', P_6170D,
                 'n17d-user', '{{#6002.query_text#}}', -220, 580))
nodes.append(ifelse('6171d', 'N17d 分发', [
    {'case_id': 'confirm_done', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_cd_d', 'value': 'CONFIRM_DONE',
                     'varType': 'string', 'variable_selector': ['6170d', 'text']}]},
    {'case_id': 'modify_existing', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'contains', 'id': 'c_me_d', 'value': 'MODIFY_EXISTING',
                     'varType': 'string', 'variable_selector': ['6170d', 'text']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_6171d_default',
                     'varType': 'string', 'variable_selector': ['6002', 'query_text']}]},
], 220, 580))

# --- N9对比 + N11询问(合并) ---
P_6173 = ('你是充电桩客服。用户确认命中的问题是他反馈的。对比他的反馈与已有记录,询问是否需要修改已有记录。\n\n'
          '【已有记录】: {{#conversation.cv_row_summary#}}\n'
          '【用户反馈】: {{#conversation.cv_feedback_zh#}}\n'
          '【本轮补充】: {{#6002.query_text#}}\n\n'
          '**规则**:\n1. 简述对比差异(若有)\n2. 询问"是否需要修改这条记录"\n3. 150字内通俗友好')
nodes.append(llm('6173', 'N9对比+N11询问修改', 'n9-sys', P_6173,
                 'n9-user', '{{#6002.query_text#}}', 480, 340))
CODE_6173T = ('def main(llm_text: str) -> dict:\n'
              '    marker = "<!--SYS:TIMER|action=arm|state=await_diff_decision-->"\n'
              '    return {"answer_text": (llm_text or "") + "\\n" + marker}\n')
nodes.append(assigner('6173-assigner', 'var_设await_diff_decision', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_await_diff_decision'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 640, 340))
nodes.append(code('6173-timer', 'N11拼TIMER标记', CODE_6173T,
                  {'answer_text': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6173', 'text']}], 840, 340))

# --- N12 汇报修改 ---
P_6175 = ('你是充电桩客服。用户确认要修改已有记录。整合用户反馈,汇报修改后内容,询问确认。\n\n'
          '【已有记录】: {{#conversation.cv_row_summary#}}\n'
          '【用户修改要求】: {{#conversation.cv_feedback_zh#}}\n'
          '【本轮补充】: {{#6002.query_text#}}\n\n'
          '**规则**:\n'
          '1. 整合出修改后的操作描述(纯内容,无问候,将写入操作描述字段)\n'
          '2. 生成汇报话术,询问"确认这样修改吗",话术150字内\n\n'
          '严格按以下格式输出两行:\n'
          '【修改后内容】<纯操作描述>\n'
          '【汇报话术】<汇报话术>')
nodes.append(llm('6175', 'N12汇报修改', 'n12-sys', P_6175,
                 'n12-user', '{{#6002.query_text#}}', 480, 460))
CODE_6175P = ('def main(llm_text: str) -> dict:\n'
              '    import re\n'
              '    t = llm_text or ""\n'
              '    m1 = re.search(r"【修改后内容】(.+?)(【汇报话术】|$)", t, re.S)\n'
              '    m2 = re.search(r"【汇报话术】(.+)", t, re.S)\n'
              '    content = m1.group(1).strip() if m1 else t\n'
              '    huibao = m2.group(1).strip() if m2 else t\n'
              '    return {"content": content, "huibao": huibao}\n')
nodes.append(code('6175-parse', 'N12解析修改内容', CODE_6175P,
                  {'content': out_str(), 'huibao': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6175', 'text']}], 740, 460))
nodes.append(assigner('6175-assigner', 'var_存修改后内容+设await_confirm_modify', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6175-parse', 'content'],
     'variable_selector': ['conversation', 'cv_feedback_zh']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_await_confirm_modify'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 1000, 460))
CODE_6175T = ('def main(huibao: str) -> dict:\n'
              '    marker = "<!--SYS:TIMER|action=arm|state=await_confirm_modify-->"\n'
              '    return {"answer_text": (huibao or "") + "\\n" + marker}\n')
nodes.append(code('6175-timer', 'N12拼TIMER标记', CODE_6175T,
                  {'answer_text': out_str()},
                  [{'variable': 'huibao', 'value_selector': ['6175-parse', 'huibao']}], 1260, 460))

# --- N14 写主表 update ---
CODE_6176A = ('def main(record_id: str, feedback_zh: str) -> dict:\n'
              '    import json\n'
              '    fields = {}\n'
              '    if feedback_zh:\n'
              '        fields["操作描述"] = feedback_zh[:2000]\n'
              '        fields["产品备注"] = feedback_zh[:500]\n'
              '    return {"body_json": json.dumps({"record_id": record_id, "fields": fields}, ensure_ascii=False)}\n')
nodes.append(code('6176a', 'N14组装update fields', CODE_6176A,
                  {'body_json': out_str()},
                  [{'variable': 'record_id', 'value_selector': ['conversation', 'cv_record_id']},
                   {'variable': 'feedback_zh', 'value_selector': ['conversation', 'cv_feedback_zh']}], 480, 580))
nodes.append(http('6176b', 'N14写主表update(飞书)',
                  'http://120.55.45.59:8501/internal/bugtrack/update',
                  '{{#6176a.body_json#}}', 740, 580))
nodes.append(assigner('6176c', 'var_设IDLE', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_idle'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 1000, 580))
CODE_6176D = ('def main(record_id: str) -> dict:\n'
              '    rid = record_id or ""\n'
              '    text = "已为您更新该问题记录(编号" + rid + "),我们将继续跟进处理,感谢您的反馈。"\n'
              '    return {"answer_text": text + "\\n<!--SYS:TIMER|action=cancel-->"}\n')
nodes.append(code('6176d', 'N14汇报+cancel', CODE_6176D,
                  {'answer_text': out_str()},
                  [{'variable': 'record_id', 'value_selector': ['conversation', 'cv_record_id']}], 1260, 580))

# --- DENY_IDENTITY 转新增(独立转写链,不查表) ---
P_6177 = ('你是 B 端 SaaS 产品客户反馈转写引擎。将用户反馈转为结构化数据。\n\n'
          '【输入】用户反馈: {{#6002.query_text#}}\n\n'
          '严格输出 JSON,仅含 mokuai/caozuomiaoshu/huanjing/leixing 四个字段,无额外说明:\n'
          '{\n'
          '  "mokuai": "模块标准名称(15字以内,无法识别填待确认)",\n'
          '  "caozuomiaoshu": "标准化操作路径与问题现象描述(80字以内)",\n'
          '  "huanjing": "后台/管家端/用户端(无法判定填待确认)",\n'
          '  "leixing": "bug/优化(无法判定填待确认)"\n'
          '}')
nodes.append(llm('6177', 'N5c 转写(否认命中转新增)', 'n5c-sys', P_6177,
                 'n5c-user', '{{#6002.query_text#}}', 480, 220))
CODE_6177P = ('def main(llm_text: str) -> dict:\n'
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
nodes.append(code('6177-parse', 'N5c解析JSON', CODE_6177P,
                  {'mokuai': out_str(), 'caozuomiaoshu': out_str(), 'huanjing': out_str(), 'leixing': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6177', 'text']}], 740, 220))
nodes.append(assigner('6177-assigner', 'var_否认转新增设cv', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6177-parse', 'mokuai'],
     'variable_selector': ['conversation', 'cv_mokuai']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6177-parse', 'huanjing'],
     'variable_selector': ['conversation', 'cv_huanjing']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6177-parse', 'leixing'],
     'variable_selector': ['conversation', 'cv_leixing']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6177-parse', 'caozuomiaoshu'],
     'variable_selector': ['conversation', 'cv_feedback_zh']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_await_confirm_new'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 1000, 220))

# ==================== 6. 新边 ====================
NEW_EDGES = [
    # 6240build 查表组装
    edge('e-6250-parse-6240build', '6250-parse', '6240build', 'source', 'code', 'code'),
    edge('e-6240build-6240', '6240build', '6240', 'source', 'code', 'http-request'),
    # 命中首轮
    edge('e-6242b-6242c', '6242b', '6242c', 'source', 'variable-assigner', 'code'),
    edge('e-6242c-6098', '6242c', '6098', 'source', 'code', 'answer'),
    # 6601 新出边
    edge('e-6601-await_confirm_identity-6170b', '6601', '6170b', 'await_confirm_identity', 'if-else', 'llm'),
    edge('e-6601-await_diff_decision-6170c', '6601', '6170c', 'await_diff_decision', 'if-else', 'llm'),
    edge('e-6601-await_confirm_modify-6170d', '6601', '6170d', 'await_confirm_modify', 'if-else', 'llm'),
    edge('e-6601-default-6003', '6601', '6003', 'default', 'if-else', 'if-else'),
    # N17b 链
    edge('e-6170b-6171b', '6170b', '6171b', 'source', 'llm', 'if-else'),
    edge('e-6171b-confirm_identity-6173', '6171b', '6173', 'confirm_identity', 'if-else', 'llm'),
    edge('e-6171b-modify_existing-6173', '6171b', '6173', 'modify_existing', 'if-else', 'llm'),
    edge('e-6171b-deny_identity-6177', '6171b', '6177', 'deny_identity', 'if-else', 'llm'),
    edge('e-6171b-default-6162', '6171b', '6162', 'default', 'if-else', 'variable-assigner'),
    # N17c 链
    edge('e-6170c-6171c', '6170c', '6171c', 'source', 'llm', 'if-else'),
    edge('e-6171c-confirm_modify-6175', '6171c', '6175', 'confirm_modify', 'if-else', 'llm'),
    edge('e-6171c-modify_existing-6175', '6171c', '6175', 'modify_existing', 'if-else', 'llm'),
    edge('e-6171c-default-6162', '6171c', '6162', 'default', 'if-else', 'variable-assigner'),
    # N17d 链
    edge('e-6170d-6171d', '6170d', '6171d', 'source', 'llm', 'if-else'),
    edge('e-6171d-confirm_done-6176a', '6171d', '6176a', 'confirm_done', 'if-else', 'code'),
    edge('e-6171d-modify_existing-6175', '6171d', '6175', 'modify_existing', 'if-else', 'llm'),
    edge('e-6171d-default-6162', '6171d', '6162', 'default', 'if-else', 'variable-assigner'),
    # N9+N11
    edge('e-6173-6173-assigner', '6173', '6173-assigner', 'source', 'llm', 'variable-assigner'),
    edge('e-6173-assigner-6173-timer', '6173-assigner', '6173-timer', 'source', 'variable-assigner', 'code'),
    edge('e-6173-timer-6098', '6173-timer', '6098', 'source', 'code', 'answer'),
    # N12
    edge('e-6175-6175-parse', '6175', '6175-parse', 'source', 'llm', 'code'),
    edge('e-6175-parse-6175-assigner', '6175-parse', '6175-assigner', 'source', 'code', 'variable-assigner'),
    edge('e-6175-assigner-6175-timer', '6175-assigner', '6175-timer', 'source', 'variable-assigner', 'code'),
    edge('e-6175-timer-6098', '6175-timer', '6098', 'source', 'code', 'answer'),
    # N14 update
    edge('e-6176a-6176b', '6176a', '6176b', 'source', 'code', 'http-request'),
    edge('e-6176b-6176c', '6176b', '6176c', 'source', 'http-request', 'variable-assigner'),
    edge('e-6176c-6176d', '6176c', '6176d', 'source', 'variable-assigner', 'code'),
    edge('e-6176d-6098', '6176d', '6098', 'source', 'code', 'answer'),
    # DENY 转新增
    edge('e-6177-6177-parse', '6177', '6177-parse', 'source', 'llm', 'code'),
    edge('e-6177-parse-6177-assigner', '6177-parse', '6177-assigner', 'source', 'code', 'variable-assigner'),
    edge('e-6177-assigner-6244', '6177-assigner', '6244', 'source', 'variable-assigner', 'llm'),
]
for e in NEW_EDGES:
    edges.append(e)

# ==================== dump ====================
with open(V18, 'w') as f:
    yaml.dump(data, f)

print('v18 generated:', V18)
print('nodes:', len(nodes), 'edges:', len(edges))
