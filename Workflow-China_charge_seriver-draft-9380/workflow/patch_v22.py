#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""缺口3 patch (修复版): 从 v21.yml 生成 v22.yml (R1/R2 汇报补飞书表记录链接)

v22 初版把 feishu_base_url 放 6901 常量, code 节点引用 [6901, feishu_base_url]
→ Dify 报"无效变量": code 节点只能引用祖先节点输出/会话变量/sys, 6901 无边非祖先。
修复: URL 直接硬编码进 6262b/6176d 的 code (URL 是稳定常量, 真实 tenant=my)。

真实 URL (用户提供): https://my.feishu.cn/base/Vi5lbLUxtaqFIBsxTvacVweRnVb?table=tbl1XIU7FSCvsTLk&view=vewP9vGR2m
记录链接 = 上述 + &record={record_id}

改:
  1. 6262b (N16汇报拼cancel): 加 record_id[6260c], code 内硬编码 URL 拼"记录链接:"
  2. 6176d (N14汇报+cancel): code 内硬编码 URL 拼"记录链接:"
不动 6901 (不再加 feishu_base_url 常量)。
"""
from ruamel.yaml import YAML

V21 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v21.yml'
V22 = '/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/charge_charging_v22.yml'

# 硬编码 URL 前缀 (真实 tenant=my, 含 view), code 内拼接 record_id
FEISHU_BASE = 'https://my.feishu.cn/base/Vi5lbLUxtaqFIBsxTvacVweRnVb?table=tbl1XIU7FSCvsTLk&view=vewP9vGR2m&record='

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

with open(V21) as f:
    data = yaml.load(f)

graph = data['workflow']['graph']
nodes = graph['nodes']
edges = graph['edges']


def find_node(nid):
    for n in nodes:
        if n['id'] == nid:
            return n
    raise KeyError('node not found: ' + nid)


# ==================== 1. 6262b: 加 record_id, code 硬编码 URL 拼链接 ====================
n6262b = find_node('6262b')
n6262b['data']['code'] = (
    'def main(llm_text: str, record_id: str) -> dict:\n'
    '    rid = (record_id or "").strip()\n'
    '    base = "' + FEISHU_BASE + '"\n'
    '    link = ("\\n记录链接: " + base + rid) if rid else ""\n'
    '    return {"answer_text": (llm_text or "") + link + "\\n<!--SYS:TIMER|action=cancel-->"}\n'
)
n6262b['data']['variables'] = [
    {'variable': 'llm_text', 'value_selector': ['6262', 'text']},
    {'variable': 'record_id', 'value_selector': ['6260c', 'record_id']},
]

# ==================== 2. 6176d: code 硬编码 URL 拼链接 ====================
n6176d = find_node('6176d')
n6176d['data']['code'] = (
    'def main(record_id: str) -> dict:\n'
    '    rid = (record_id or "").strip()\n'
    '    base = "' + FEISHU_BASE + '"\n'
    '    text = "已为您更新该问题记录(编号" + rid + "),我们将继续跟进处理,感谢您的反馈。"\n'
    '    link = ("\\n记录链接: " + base + rid) if rid else ""\n'
    '    return {"answer_text": text + link + "\\n<!--SYS:TIMER|action=cancel-->"}\n'
)
# 6176d 原有 variables = [record_id [conversation, cv_record_id]], 保持不变 (不加 feishu_base_url)

# ==================== dump ====================
with open(V22, 'w') as f:
    yaml.dump(data, f)

# ==================== 校验 ====================
import ast
for nid in ['6262b', '6176d']:
    ast.parse(find_node(nid)['data']['code'])  # SyntaxError 会抛
# 6262b vars 不含 6901 引用
vs6262b = [v['value_selector'] for v in find_node('6262b')['data']['variables']]
assert not any(vs[0] == '6901' for vs in vs6262b), '6262b still refs 6901'
# 6176d vars 不含 6901 引用
vs6176d = [v['value_selector'] for v in find_node('6176d')['data']['variables']]
assert not any(vs[0] == '6901' for vs in vs6176d), '6176d still refs 6901'
# 6901 不含 feishu_base_url (本版不改 6901)
assert 'feishu_base_url' not in find_node('6901')['data']['outputs']
# code 含真实 URL
assert 'my.feishu.cn' in find_node('6262b')['data']['code']
assert 'my.feishu.cn' in find_node('6176d')['data']['code']
# 边端点存在
idset = set(n['id'] for n in nodes)
for e in edges:
    assert e['source'] in idset and e['target'] in idset, 'dangling edge: ' + e['id']

print('v22 regenerated (fixed):', V22)
print('nodes:', len(nodes), 'edges:', len(edges))
print('6262b vars:', vs6262b)
print('6176d vars:', vs6176d)
print('6901 outputs (应无 feishu_base_url):', 'feishu_base_url' in find_node('6901')['data']['outputs'])
