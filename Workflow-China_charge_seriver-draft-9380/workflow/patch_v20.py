#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次二.4 patch: 从 v19.yml 生成 v20.yml (信息充足度判定 + 引导补充循环)

目标: 按 新反馈增加.txt, N5/N5b 提取前先判定信息充足度:
  - 充足  → 正常提取四字段 → 查表 → 确认 (现状不变)
  - 不足  → 只输出引导话术(不生成结构化数据), 设 await_confirm_new + 存原始反馈
            + cv_clarify_count=1, 等用户补充
  - 补充后 → 复用现有 MODIFY_NEW 链 (6172合并→6250b) → 6250b 再次判定
  - 最多引导2次, 第3次仍不足 → 兜底"待确认"四字段 (6250b-judge 输出 FALLBACK)

改: 6250/6250b prompt 升级完整版 + 6250b-parse 加 FALLBACK 兜底 + 6901 加 clarify_count_1
加: cv_clarify_count 会话变量 + 8 新节点
    (6250-judge/if/insuf/insuf-out + 6250b-judge/if/insuf/insuf-out)
改边: 删 6250→6250-parse / 6250b→6250b-parse, 加 14 新边, 6098 variables 加2成员
"""
from ruamel.yaml import YAML

V19 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v19.yml'
V20 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v20.yml'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V19) as f:
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


def out_num():
    return {'children': None, 'type': 'number'}


# ==================== 1. 加 cv_clarify_count 会话变量 ====================
cv_vars = data['workflow']['conversation_variables']
cv_vars.append({
    'description': '信息不足引导补充计数(0=未引导,1=引导1次,2=引导2次,>=2触发兜底待确认)',
    'id': 'a1b2c3d4-0001-4000-8000-000000000004',
    'name': 'cv_clarify_count',
    'value': 0,
    'value_type': 'number',
})

# ==================== 2. 6901 加 clarify_count_1 常量 (assigner 不支持 constant, 经 6901 引用) ====================
n6901 = find_node('6901')
n6901['data']['code'] = n6901['data']['code'].replace(
    '"str_await_modify_window": "await_modify_window"',
    '"str_await_modify_window": "await_modify_window",\n        "clarify_count_0": 0,\n        "clarify_count_1": 1'
)
n6901['data']['outputs']['clarify_count_0'] = out_num()
n6901['data']['outputs']['clarify_count_1'] = out_num()

# ==================== 3. 升级 6250 (N5) prompt 为完整版 (首次反馈) ====================
P_N5_SYS = (
    '你是 B 端 SaaS 产品客户反馈一体化处理引擎,承接客户原始反馈。核心职责:\n'
    '1. 前置判定信息充足度,不足时只输出引导话术(不生成结构化数据),绝不脑补\n'
    '2. 充足时提取 mokuai/caozuomiaoshu/huanjing/leixing 四字段结构化数据\n'
    '3. 生成客户侧确认话术\n\n'
    '【输入】用户反馈: {{#6002.query_text#}}\n\n'
    '【信息充足度判定】满足任意1条即判为"信息不足":\n'
    '1. 模块/场景完全不明确:仅"系统有问题""充电桩用不了",无法定位具体功能/页面/业务场景\n'
    '2. 问题现象过于笼统:仅"注册不了""充不了电",无操作路径/报错原文/触发条件/异常表现\n'
    '3. 终端环境不明确:仅"移动端有问题""后台出错",无法区分用户端APP/管家端APP/web管理后台\n'
    '4. 诉求属性不明确:仅"功能不好用""显示有问题",无法区分功能故障(bug)还是优化建议/新增需求\n'
    '5. 完全无有效业务信息:仅情绪宣泄/催促/问候,无任何问题相关实质内容\n\n'
    '【输出规范】必须先输出【充足度】标签,再按场景输出:\n\n'
    '若信息充足:\n'
    '【充足度】SUFFICIENT\n'
    '【内部结构化数据】\n'
    '{"mokuai":"模块标准名称(15字以内,无法识别填待确认)","caozuomiaoshu":"标准化操作路径与问题现象描述(80字以内,结构:操作终端+操作路径+执行动作+问题现象+业务影响,过滤情绪废话)","huanjing":"后台/管家端/用户端(无法判定填待确认)","leixing":"bug/优化(无法判定填待确认)"}\n'
    '【客户侧回复话术】\n'
    '正式亲和语气,无技术黑话。结构:开篇问候(已收到并整理)+核心信息分点(模块/问题描述通俗化/终端环境/类型,bug译为功能故障,优化译为优化建议)+主动确认(询问记录是否准确)+补充提示(若有遗漏可告知)+礼貌收尾\n\n'
    '若信息不足:\n'
    '【充足度】INSUFFICIENT\n'
    '【客户侧引导话术】\n'
    '针对缺失信息点精准提问(缺什么问什么,不泛泛要求补充细节),末尾统一追加"如果您有相关的用户ID、订单ID、充电桩编号,也可以一并提供,能帮助我们更快定位排查问题"。专业耐心,不质问不敷衍。参考场景:\n'
    '- 模块不明:问属于哪个业务功能/场景(充电桩设备管理/订单财务结算/用户运营/场站相关)\n'
    '- 现象笼统:问具体操作步骤+异常现象(报错提示/页面显示异常/操作无响应)\n'
    '- 终端不明:问在哪个终端操作(web管理后台/管家端APP/用户端APP)\n'
    '- 属性不明:问是功能故障还是优化建议/新增需求\n'
    '- 无有效信息:请描述 1.操作的功能/页面 2.异常现象 3.使用的终端\n\n'
    '【全局约束】\n'
    '- 100%基于输入文本,不脑补不编造未提及的信息\n'
    '- 枚举字段严格遵守可选值范围,不得自定义\n'
    '- 客户回复只做信息同步与确认,不做排期/解决方案承诺\n'
    '- 必须输出【充足度】SUFFICIENT 或【充足度】INSUFFICIENT 标签'
)
n6250 = find_node('6250')
n6250['data']['prompt_template'][0]['text'] = P_N5_SYS

# ==================== 4. 升级 6250b (N5b) prompt 为完整版 (迭代场景) ====================
P_N5B_SYS = (
    '你是 B 端 SaaS 产品客户反馈一体化处理引擎。当前是【迭代场景】:已有一轮反馈整理,用户现在补充/修改信息,需整合后重新判定。\n\n'
    '【输入】整合后的反馈(已有反馈+用户补充): {{#6172.merged#}}\n\n'
    '【信息充足度判定】满足任意1条即判为"信息不足":\n'
    '1. 模块/场景完全不明确(无法定位具体功能/页面)\n'
    '2. 问题现象过于笼统(无操作路径/报错原文/触发条件)\n'
    '3. 终端环境不明确(无法区分用户端/管家端/后台)\n'
    '4. 诉求属性不明确(无法区分bug还是优化)\n'
    '5. 完全无有效业务信息\n\n'
    '【迭代修正规则】若用户补充了修改要求,100%按客户要求修正对应字段:\n'
    '- 模块归属错误→调整mokuai为客户指定名称\n'
    '- 描述偏差/遗漏→修正caozuomiaoshu对应内容\n'
    '- 环境/类型错误→同步调整huanjing、leixing\n'
    '- 客户未提及的字段保留原值,不变动\n\n'
    '【输出规范】必须先输出【充足度】标签:\n\n'
    '若信息充足:\n'
    '【充足度】SUFFICIENT\n'
    '【内部结构化数据】\n'
    '{"mokuai":"模块标准名称(15字以内,无法识别填待确认)","caozuomiaoshu":"标准化操作路径与问题现象描述(80字以内,结构:操作终端+操作路径+执行动作+问题现象+业务影响)","huanjing":"后台/管家端/用户端(无法判定填待确认)","leixing":"bug/优化(无法判定填待确认)"}\n'
    '【客户侧回复话术】\n'
    '告知已根据补充内容更新记录,同步调整后的内容请客户确认(开篇+4字段通俗描述,bug译为功能故障,优化译为优化建议+确认+补充提示+收尾)\n\n'
    '若信息不足:\n'
    '【充足度】INSUFFICIENT\n'
    '【客户侧引导话术】\n'
    '针对仍缺失的信息点精准提问,末尾追加用户ID/订单ID/充电桩编号提示\n\n'
    '【全局约束】\n'
    '- 100%基于输入文本,不脑补不编造\n'
    '- 枚举字段严格遵守可选值范围\n'
    '- 客户回复只做信息同步与确认,不做排期/解决方案承诺\n'
    '- 必须输出【充足度】SUFFICIENT 或【充足度】INSUFFICIENT 标签'
)
n6250b = find_node('6250b')
n6250b['data']['prompt_template'][0]['text'] = P_N5B_SYS

# ==================== 5. 改 6250b-parse: 加 label 输入 + FALLBACK 兜底返回待确认 ====================
n6250bp = find_node('6250b-parse')
n6250bp['data']['code'] = (
    'def main(llm_text: str, label: str) -> dict:\n'
    '    import json, re\n'
    '    if label == "FALLBACK":\n'
    '        return {"mokuai":"待确认","caozuomiaoshu":"待确认","huanjing":"待确认","leixing":"待确认"}\n'
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
    '        return {"mokuai":"","caozuomiaoshu":"","huanjing":"","leixing":""}\n'
)
n6250bp['data']['variables'] = [
    {'variable': 'llm_text', 'value_selector': ['6250b', 'text']},
    {'variable': 'label', 'value_selector': ['6250b-judge', 'label']},
]

# ==================== 5b. 6243 加重置 cv_clarify_count=0 (首次充足提取后清零, 避免残留导致下轮 6250b 兜底误判) ====================
n6243 = find_node('6243')
n6243['data']['items'].append({
    'input_type': 'variable', 'operation': 'over-write',
    'value': ['6901', 'clarify_count_0'],
    'variable_selector': ['conversation', 'cv_clarify_count'],
})

# ==================== 6. 8 新节点 ====================
# --- 6250-judge: 解析 N5 输出的充足度标签 ---
CODE_6250J = (
    'def main(llm_text: str) -> dict:\n'
    '    import re\n'
    '    text = llm_text or ""\n'
    '    t = text.upper()\n'
    '    if "INSUFFICIENT" in t:\n'
    '        label = "INSUFFICIENT"\n'
    '    elif "SUFFICIENT" in t:\n'
    '        label = "SUFFICIENT"\n'
    '    else:\n'
    '        label = "SUFFICIENT" if re.search(r"\\{[^{}]*\\}", text) else "INSUFFICIENT"\n'
    '    return {"label": label}\n'
)
nodes.append(code('6250-judge', 'N5充足度判定', CODE_6250J,
                  {'label': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6250', 'text']}],
                  1380, 860))

# --- 6250-if: N5 充足度分支 ---
nodes.append(ifelse('6250-if', 'N5充足度分支', [
    {'case_id': 'sufficient', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'is', 'id': 'c_suf_6250', 'value': 'SUFFICIENT',
                     'varType': 'string', 'variable_selector': ['6250-judge', 'label']}]},
    {'case_id': 'insufficient', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'is', 'id': 'c_ins_6250', 'value': 'INSUFFICIENT',
                     'varType': 'string', 'variable_selector': ['6250-judge', 'label']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_6250_default',
                     'varType': 'string', 'variable_selector': ['6002', 'query_text']}]},
], 1560, 860))

# --- 6250-insuf: 不足时设态 + 存原始反馈 + count=1 ---
nodes.append(assigner('6250-insuf', 'N5不足设态+存原始反馈', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_await_confirm_new'],
     'variable_selector': ['conversation', 'cv_flow_state']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6002', 'query_text'],
     'variable_selector': ['conversation', 'cv_feedback_zh']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'clarify_count_1'],
     'variable_selector': ['conversation', 'cv_clarify_count']},
], 1560, 980))

# --- 6250-insuf-out: 引导话术包成 answer_text (过滤内部标签 + 拼 TIMER 标记) ---
CODE_INSUF_OUT = (
    'def main(llm_text: str) -> dict:\n'
    '    import re\n'
    '    text = llm_text or ""\n'
    '    text = re.sub(r"【充足度】[^\\n]*\\n?", "", text)\n'
    '    text = re.sub(r"【客户侧引导话术】\\s*\\n?", "", text)\n'
    '    text = re.sub(r"【内部结构化数据】[^\\n]*\\n?", "", text)\n'
    '    text = re.sub(r"【客户侧回复话术】\\s*\\n?", "", text)\n'
    '    text = re.sub(r"\\{[^{}]*\\}", "", text)\n'
    '    text = re.sub(r"(?m)^\\s*(SUFFICIENT|INSUFFICIENT)\\s*$", "", text)\n'
    '    text = re.sub(r"\\n{3,}", "\\n\\n", text)\n'
    '    text = text.strip()\n'
    '    marker = "<!--SYS:TIMER|action=arm|state=await_confirm_new-->"\n'
    '    return {"answer_text": text + "\\n" + marker}\n'
)
nodes.append(code('6250-insuf-out', 'N5引导话术直出', CODE_INSUF_OUT,
                  {'answer_text': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6250', 'text']}],
                  1560, 1100))

# --- 6250b-judge: 解析 N5b 标签 + 计数兜底(count>=2 且不足→FALLBACK) ---
CODE_6250BJ = (
    'def main(llm_text: str, clarify_count) -> dict:\n'
    '    import re\n'
    '    text = llm_text or ""\n'
    '    t = text.upper()\n'
    '    if "INSUFFICIENT" in t:\n'
    '        is_suf = False\n'
    '    elif "SUFFICIENT" in t:\n'
    '        is_suf = True\n'
    '    else:\n'
    '        is_suf = bool(re.search(r"\\{[^{}]*\\}", text))\n'
    '    try:\n'
    '        count = int(clarify_count or 0)\n'
    '    except Exception:\n'
    '        count = 0\n'
    '    if (not is_suf) and count >= 2:\n'
    '        return {"label": "FALLBACK", "next_count": count}\n'
    '    if is_suf:\n'
    '        return {"label": "SUFFICIENT", "next_count": count}\n'
    '    return {"label": "INSUFFICIENT", "next_count": count + 1}\n'
)
nodes.append(code('6250b-judge', 'N5b充足度判定+兜底', CODE_6250BJ,
                  {'label': out_str(), 'next_count': out_num()},
                  [{'variable': 'llm_text', 'value_selector': ['6250b', 'text']},
                   {'variable': 'clarify_count', 'value_selector': ['conversation', 'cv_clarify_count']}],
                  740, 540))

# --- 6250b-if: N5b 充足度三分支 (sufficient/fallback 都→6250b-parse) ---
nodes.append(ifelse('6250b-if', 'N5b充足度分支', [
    {'case_id': 'sufficient', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'is', 'id': 'c_suf_6250b', 'value': 'SUFFICIENT',
                     'varType': 'string', 'variable_selector': ['6250b-judge', 'label']}]},
    {'case_id': 'fallback', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'is', 'id': 'c_fb_6250b', 'value': 'FALLBACK',
                     'varType': 'string', 'variable_selector': ['6250b-judge', 'label']}]},
    {'case_id': 'insufficient', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'is', 'id': 'c_ins_6250b', 'value': 'INSUFFICIENT',
                     'varType': 'string', 'variable_selector': ['6250b-judge', 'label']}]},
    {'case_id': 'default', 'logical_operator': 'and',
     'conditions': [{'comparison_operator': 'not empty', 'id': 'cond_6250b_default',
                     'varType': 'string', 'variable_selector': ['6002', 'query_text']}]},
], 920, 540))

# --- 6250b-insuf: 不足且 count<2 时计数+1 + 累积 merged 到 cv_feedback_zh + 保持态 ---
nodes.append(assigner('6250b-insuf', 'N5b不足计数+累积补充', [
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6250b-judge', 'next_count'],
     'variable_selector': ['conversation', 'cv_clarify_count']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6172', 'merged'],
     'variable_selector': ['conversation', 'cv_feedback_zh']},
    {'input_type': 'variable', 'operation': 'over-write',
     'value': ['6901', 'str_await_confirm_new'],
     'variable_selector': ['conversation', 'cv_flow_state']},
], 920, 660))

# --- 6250b-insuf-out: 引导话术包成 answer_text ---
nodes.append(code('6250b-insuf-out', 'N5b引导话术直出', CODE_INSUF_OUT,
                  {'answer_text': out_str()},
                  [{'variable': 'llm_text', 'value_selector': ['6250b', 'text']}],
                  920, 780))

# ==================== 7. 删边 + 加边 ====================
# 删 6250→6250-parse, 6250b→6250b-parse (改为经 judge/if 分支)
edges[:] = [e for e in edges if not (e['source'] == '6250' and e['target'] == '6250-parse')]
edges[:] = [e for e in edges if not (e['source'] == '6250b' and e['target'] == '6250b-parse')]

NEW_EDGES = [
    # N5 分支
    edge('e-6250-6250judge', '6250', '6250-judge', 'source', 'llm', 'code'),
    edge('e-6250judge-6250if', '6250-judge', '6250-if', 'source', 'code', 'if-else'),
    edge('e-6250if-suf-6250parse', '6250-if', '6250-parse', 'sufficient', 'if-else', 'code'),
    edge('e-6250if-def-6250parse', '6250-if', '6250-parse', 'default', 'if-else', 'code'),
    edge('e-6250if-ins-6250insuf', '6250-if', '6250-insuf', 'insufficient', 'if-else', 'variable-assigner'),
    edge('e-6250insuf-6250insufout', '6250-insuf', '6250-insuf-out', 'source', 'variable-assigner', 'code'),
    edge('e-6250insufout-6098', '6250-insuf-out', '6098', 'source', 'code', 'answer'),
    # N5b 分支
    edge('e-6250b-6250bjudge', '6250b', '6250b-judge', 'source', 'llm', 'code'),
    edge('e-6250bjudge-6250bif', '6250b-judge', '6250b-if', 'source', 'code', 'if-else'),
    edge('e-6250bif-suf-6250bparse', '6250b-if', '6250b-parse', 'sufficient', 'if-else', 'code'),
    edge('e-6250bif-fb-6250bparse', '6250b-if', '6250b-parse', 'fallback', 'if-else', 'code'),
    edge('e-6250bif-def-6250bparse', '6250b-if', '6250b-parse', 'default', 'if-else', 'code'),
    edge('e-6250bif-ins-6250binsuf', '6250b-if', '6250b-insuf', 'insufficient', 'if-else', 'variable-assigner'),
    edge('e-6250binsuf-6250binsufout', '6250b-insuf', '6250b-insuf-out', 'source', 'variable-assigner', 'code'),
    edge('e-6250binsufout-6098', '6250b-insuf-out', '6098', 'source', 'code', 'answer'),
]
for e in NEW_EDGES:
    edges.append(e)

# ==================== 8. 6098 variables 加2成员 (汇聚引导话术 answer_text) ====================
n6098 = find_node('6098')
n6098['data']['variables'].append(['6250-insuf-out', 'answer_text'])
n6098['data']['variables'].append(['6250b-insuf-out', 'answer_text'])

# ==================== 9. 流程重构: 先查表再判定充足度 (V6 行为变化) ====================
# N5 总是提取(内部用) → 先查表 → 命中走D4汇报 / 未命中再按充足度分支
# 这样模糊反馈(如"订单没有支付时间")也能靠模块名命中已有记录,而非直接引导
# N5b(迭代场景)不查表,保持原样

# 9.1 N5 prompt 改: 总是输出 JSON + 充足度标签 + 话术(不足时字段填待确认,但尽量识别模块名)
P_N5_SYS_V2 = (
    '你是 B 端 SaaS 产品客户反馈一体化处理引擎,承接客户原始反馈。核心职责:\n'
    '1. 提取 mokuai/caozuomiaoshu/huanjing/leixing 四字段(总是提取,信息不足字段填"待确认",但应尽量识别模块名)\n'
    '2. 判定信息充足度,不足时生成引导话术;充足时生成确认话术\n\n'
    '【输入】用户反馈: {{#6002.query_text#}}\n\n'
    '【信息充足度判定】满足任意1条即"信息不足":\n'
    '1. 模块/场景完全不明确(仅"系统有问题""充电桩用不了",无法定位具体功能/页面)\n'
    '2. 问题现象过于笼统(仅"注册不了""充不了电",无操作路径/报错原文/触发条件)\n'
    '3. 终端环境不明确(无法区分用户端/管家端/后台)\n'
    '4. 诉求属性不明确(无法区分bug还是优化)\n'
    '5. 完全无有效业务信息\n'
    '注意:即使整体信息不足,只要能识别出模块名(如"订单""充电""支付"),mokuai 必须填该模块名,不要填"待确认"。\n\n'
    '【输出规范】严格按以下结构输出(顺序不变):\n'
    '【充足度】SUFFICIENT 或 INSUFFICIENT\n'
    '【内部结构化数据】\n'
    '{"mokuai":"模块标准名称(15字以内,无法识别填待确认,但尽量识别)","caozuomiaoshu":"标准化操作路径与问题现象描述(80字以内,结构:操作终端+操作路径+执行动作+问题现象+业务影响,过滤情绪废话)","huanjing":"后台/管家端/用户端(无法判定填待确认)","leixing":"bug/优化(无法判定填待确认)"}\n\n'
    '若【充足度】INSUFFICIENT,继续输出:\n'
    '【客户侧引导话术】\n'
    '针对缺失信息点精准提问(缺什么问什么),末尾追加"如果您有相关的用户ID、订单ID、充电桩编号,也可以一并提供,能帮助我们更快定位排查问题"。参考:模块不明问业务场景;现象笼统问操作步骤+异常现象;终端不明问web管理后台/管家端APP/用户端APP;属性不明问功能故障还是优化建议;无信息问1.功能页面 2.异常现象 3.终端。\n\n'
    '若【充足度】SUFFICIENT,继续输出:\n'
    '【客户侧回复话术】\n'
    '正式亲和语气,无技术黑话。结构:开篇问候+4字段通俗描述(bug译为功能故障,优化译为优化建议)+主动确认+补充提示+礼貌收尾。\n\n'
    '【全局约束】\n'
    '- 100%基于输入文本,不脑补不编造\n'
    '- 枚举字段严格遵守可选值范围\n'
    '- 客户回复只做信息同步与确认,不做排期/解决方案承诺\n'
    '- 必须输出【充足度】SUFFICIENT 或【充足度】INSUFFICIENT 标签'
)
n6250['data']['prompt_template'][0]['text'] = P_N5_SYS_V2

# 9.2 6250-judge 改: 输出 label + 四字段(供 6240build 查表 + 6243 写 cv)
CODE_6250J_V2 = (
    'def main(llm_text: str) -> dict:\n'
    '    import json, re\n'
    '    text = llm_text or ""\n'
    '    t = text.upper()\n'
    '    if "INSUFFICIENT" in t:\n'
    '        label = "INSUFFICIENT"\n'
    '    elif "SUFFICIENT" in t:\n'
    '        label = "SUFFICIENT"\n'
    '    else:\n'
    '        label = "SUFFICIENT" if re.search(r"\\{[^{}]*\\}", text) else "INSUFFICIENT"\n'
    '    mokuai=caozuomiaoshu=huanjing=leixing=""\n'
    '    m = re.search(r"\\{[^{}]*\\}", text)\n'
    '    if m:\n'
    '        try:\n'
    '            obj = json.loads(m.group(0))\n'
    '            mokuai=str(obj.get("mokuai","")).strip()[:50]\n'
    '            caozuomiaoshu=str(obj.get("caozuomiaoshu","")).strip()[:500]\n'
    '            huanjing=str(obj.get("huanjing","")).strip()[:20]\n'
    '            leixing=str(obj.get("leixing","")).strip()[:20]\n'
    '        except Exception:\n'
    '            pass\n'
    '    return {"label": label, "mokuai": mokuai, "caozuomiaoshu": caozuomiaoshu, "huanjing": huanjing, "leixing": leixing}\n'
)
n6250j = find_node('6250-judge')
n6250j['data']['code'] = CODE_6250J_V2
n6250j['data']['outputs'] = {
    'label': out_str(), 'mokuai': out_str(), 'caozuomiaoshu': out_str(),
    'huanjing': out_str(), 'leixing': out_str(),
}

# 9.3 删 6250-parse (被 6250-judge 取代, 四字段改由 judge 输出)
nodes[:] = [n for n in nodes if n['id'] != '6250-parse']

# 9.4 6240build: mokuai 改读 6250-judge
n6240build = find_node('6240build')
for v in n6240build['data']['variables']:
    if v['variable'] == 'mokuai':
        v['value_selector'] = ['6250-judge', 'mokuai']

# 9.5 6243: 四字段 value 改读 6250-judge (原来读 6250-parse)
n6243 = find_node('6243')
for item in n6243['data']['items']:
    val = item.get('value')
    if val and len(val) == 2 and val[0] == '6250-parse':
        item['value'] = ['6250-judge', val[1]]

# 9.6 边改动: 删旧链 + 接新链
# 删: 6250-judge→6250-if, 6250-if→6250-parse, 6250-parse→6240build, 6241[default]→6243
edges[:] = [e for e in edges if not (
    (e['source'] == '6250-judge' and e['target'] == '6250-if') or
    (e['source'] == '6250-if' and e['target'] == '6250-parse') or
    (e['source'] == '6250-parse' and e['target'] == '6240build') or
    (e['source'] == '6241' and e['target'] == '6243')
)]
# 加: 6250-judge→6240build, 6241[default]→6250-if, 6250-if[sufficient/default]→6243
for e in [
    edge('e-6250judge-6240build', '6250-judge', '6240build', 'source', 'code', 'code'),
    edge('e-6241-default-6250if', '6241', '6250-if', 'default', 'if-else', 'if-else'),
    edge('e-6250if-suf-6243', '6250-if', '6243', 'sufficient', 'if-else', 'variable-assigner'),
    edge('e-6250if-def-6243', '6250-if', '6243', 'default', 'if-else', 'variable-assigner'),
]:
    edges.append(e)

# ==================== dump ====================
with open(V20, 'w') as f:
    yaml.dump(data, f)

print('v20 generated:', V20)
print('nodes:', len(nodes), 'edges:', len(edges))
