#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 工作流(KB问答)多语言自动适配 patch

角色: 自动识别用户输入语言/字符体系, 全程对应语言输出话术, 同步适配结构化字段语言。
流程: 基于整合全文自动检测自然语言, 确定目标输出语言, 适配字符集保障泰/尼泊尔等复杂脚本渲染。

改:
  1. 6002 加泰文(0x0E00-0x0E7F)+尼泊尔/天城文(0x0900-0x097F)检测
  2. 6001 select 加 th/ne 选项
  3. 面向客户 LLM(6105/6107/6111/6212/6221/6231)注入语言指令(引用 {{#6002.language#}})
  4. 6210 A2(内部检索词条)保持中文(匹配中文知识库)
"""
from ruamel.yaml import YAML

SRC = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_A.yml'
OUT = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_A.yml'

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


# ==================== 1. 6002 扩展泰/尼泊尔文检测 ====================
CODE_6002 = (
    'def main(query: str, input_language: str) -> dict:\n'
    '    text = (query or "").strip()\n'
    '    if input_language and input_language.strip():\n'
    '        lang = input_language.strip()\n'
    '    else:\n'
    '        cjk = sum(1 for c in text if \'\\u4e00\' <= c <= \'\\u9fff\')\n'
    '        # 泰文 0x0E00-0x0E7F; 尼泊尔/天城文 0x0900-0x097F\n'
    '        thai = any(0x0E00 <= ord(c) <= 0x0E7F for c in text)\n'
    '        devanagari = any(0x0900 <= ord(c) <= 0x097F for c in text)\n'
    '        vi_chars = "\\u0103\\u00e2\\u0111\\u00ea\\u00f4\\u01a1\\u01b0\\u0102\\u00c2\\u0110\\u00ca\\u00d4\\u01a0\\u01af"\n'
    '        vi_chars += "\\u00e1\\u00e0\\u1ea3\\u00e3\\u1ea1\\u1eaf\\u1eb1\\u1eb3\\u1eb5\\u1eb7\\u1ea5\\u1ea7\\u1ea9\\u1eab\\u1ead"\n'
    '        vi_chars += "\\u00e9\\u00e8\\u1ebb\\u1ebd\\u1eb9\\u1ebf\\u1ec1\\u1ec3\\u1ec5\\u1ec7\\u00ed\\u00ec\\u1ec9\\u00ee\\u1ecb"\n'
    '        vi_chars += "\\u00f3\\u00f2\\u1ecf\\u00f5\\u1ecd\\u1ed1\\u1ed3\\u1ed5\\u1ed7\\u1ed9\\u1edb\\u1edd\\u1edf\\u1ee1\\u1ee3"\n'
    '        vi_chars += "\\u00fa\\u00f9\\u1ee5\\u00fb\\u1ee7\\u1ee9\\u1eeb\\u1eed\\u1eef\\u1ef1\\u00fd\\u1ef3\\u1ef5\\u1ef7\\u1ef9"\n'
    '        if thai:\n'
    '            lang = "th"\n'
    '        elif devanagari:\n'
    '            lang = "ne"\n'
    '        elif any(c in vi_chars for c in text):\n'
    '            lang = "vi"\n'
    '        elif cjk > 0:\n'
    '            lang = "zh"\n'
    '        else:\n'
    '            lang = "en"\n'
    '    return {"query_text": text, "language": lang}\n'
)
n6002 = find_node('6002')
n6002['data']['code'] = CODE_6002

# ==================== 2. 6001 select 加 th/ne ====================
n6001 = find_node('6001')
for v in n6001['data'].get('variables', []):
    if v.get('variable') == 'input_language':
        if 'th' not in v.get('options', []):
            v['options'] = ['zh', 'en', 'vi', 'th', 'ne', '']
        if v.get('label') == '语言(可选)':
            v['label'] = '语言(可选, 留空则自动检测)'

# ==================== 3. 面向客户 LLM 注入多语言指令 ====================
SUFFIX_CUSTOMER = (
    '\n\n【多语言自动适配】\n'
    '- 自动检测用户输入的自然语言, 全程使用对应语言输出全部客户侧话术(检测语言:{{#6002.language#}}, zh/en/vi/th/ne)。\n'
    '- 使用对应语言的字符集编码, 保障泰语(th)、尼泊尔语(ne)等复杂脚本正常渲染、无乱码, 匹配用户端字体显示习惯。\n'
    '- 若检索结果原文为中文而用户语言非中文, 需将答案翻译为用户语言后输出(关键业务术语可保留中文对照)。\n'
    '- 结构化业务字段保持中文 key, value 适配用户语言。'
)

SUFFIX_A2 = (
    '\n\n【检索词条语言】\n'
    '即使用户使用其他语言输入, 检索词条须输出中文(匹配中文知识库), 3-6个逗号分隔。'
)

CUSTOMER_LLM = ['6105', '6107', '6111', '6212', '6221', '6231']
for nid in CUSTOMER_LLM:
    n = find_node(nid)
    sys_prompt = n['data']['prompt_template'][0]
    txt = sys_prompt['text']
    if '多语言自动适配' not in txt:
        sys_prompt['text'] = txt + SUFFIX_CUSTOMER

# 6210 A2 内部检索词条 - 保持中文
n6210 = find_node('6210')
sys6210 = n6210['data']['prompt_template'][0]
if '检索词条语言' not in sys6210['text']:
    sys6210['text'] = sys6210['text'] + SUFFIX_A2

with open(OUT, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
import ast
ast.parse(CODE_6002)
with open(OUT) as f:
    data2 = yaml.load(f)
nd2 = {n['id']: n for n in data2['workflow']['graph']['nodes']}
# 6002
assert 'thai' in nd2['6002']['data']['code'] and 'devanagari' in nd2['6002']['data']['code']
# 6001
opts6001 = next(v['options'] for v in nd2['6001']['data']['variables'] if v['variable'] == 'input_language')
assert 'th' in opts6001 and 'ne' in opts6001, opts6001
# LLM 注入
for nid in CUSTOMER_LLM:
    assert '多语言自动适配' in nd2[nid]['data']['prompt_template'][0]['text'], nid
    assert '{{#6002.language#}}' in nd2[nid]['data']['prompt_template'][0]['text'], nid
assert '检索词条语言' in nd2['6210']['data']['prompt_template'][0]['text']
print('A multilingual patch applied:', OUT)
print('6002 thai+devanagari detection: OK')
print('6001 options:', opts6001)
print('customer LLM injected:', CUSTOMER_LLM)
print('6210 A2 keep-Chinese: OK')
