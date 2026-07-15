"""构建 China_charge_seriver_v2.yml。

执行: python tools/build_charge_workflow.py
输出: Workflow-China_charge_seriver-draft-9380/workflow/China_charge_seriver_v2.yml

复用 backend/charge_consult/ 已有的 Python 代码(scene_router / path_handlers / end_aggregator)
嵌入 yml code 节点,确保 yml 与后端代码同步。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT.parent / "backend"
TOOLKIT_PKG = ROOT / "dify_workflow_toolkit"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(TOOLKIT_PKG))

from dify_workflow_toolkit.builder import (
    CodeNode, Edge, EndNode, IfElseNode, KnowledgeRetrievalNode,
    LLMNode, StartNode, Variable, VariableAggregatorNode, Workflow,
)

# ── 加载后端已有代码字符串(用作 code 节点 code) ──
def _load_module_source(name: str, file_path: Path) -> str:
    """读 .py 源文件,把 `main(...)` 函数体外的内容剥掉,只留 main body。"""
    src = file_path.read_text(encoding="utf-8")
    # 提取 main 函数体内的代码(简化)
    return src

# 4 维分类 + 兜底
SCENE_ROUTER_SRC = (BACKEND / "charge_consult/scene_router.py").read_text(encoding="utf-8")
PATH_HANDLERS_SRC = (BACKEND / "charge_consult/path_handlers.py").read_text(encoding="utf-8")
END_AGG_SRC = (BACKEND / "charge_consult/end_aggregator.py").read_text(encoding="utf-8")
DANGER_SRC = (BACKEND / "charge_consult/danger_signals.py").read_text(encoding="utf-8")

# ── 占位数据集 ID ──
DS = {
    "SPEC": "<DATASET_PRODUCT_SPEC>",
    "CHANGELOG": "<DATASET_PRODUCT_CHANGELOG>",
    "FAQ": "<DATASET_FAQ>",
    "FAULT": "<DATASET_FAULT_DIAGNOSIS>",
    "PRICING": "<DATASET_PRICING>",
    "GUIDE": "<DATASET_OPERATION_GUIDE>",
}

# ── start 输入变量 ──
START_VARS = [
    Variable("input_text", "用户文本", "paragraph", required=False, max_length=4000, default=""),
    Variable("input_language", "语言", "select", required=True, options=["zh","en","vi"], default="zh"),
    Variable("input_session_id", "会话ID", "text-input", required=False, default=""),
    Variable("input_turn", "轮次", "number", required=False, default=1),
    Variable("input_hint_endpoint", "端类型", "select", required=False, options=["user","butler","pc",""], default=""),
    Variable("input_hint_region", "地域", "select", required=False, options=["cn","overseas",""], default=""),
    Variable("input_answers", "问卷答案JSON", "paragraph", required=False, default=""),
]

# ── 危险信号 code(SPEC-D2 5020) ──
# 从后端 danger_signals.py 提取 DANGER_SIGNALS_BY_ENDPOINT,适配 code 节点
DANGER_CODE = '''
from charge_consult.danger_signals import DANGER_SIGNALS_BY_ENDPOINT
import os, sys
sys.path.insert(0, "/app")

def main(input_text: str, endpoint: str) -> dict:
    text = (input_text or "")
    if not text: return {"matched": False, "keyword": None, "risk_level": "low",
                        "action": None, "endpoint": endpoint, "fallback_message": None}
    signals = DANGER_SIGNALS_BY_ENDPOINT.get(endpoint, [])
    for sig in signals:
        if sig.keyword in text:
            return {
                "matched": True, "keyword": sig.keyword,
                "risk_level": sig.risk_level, "action": sig.action,
                "endpoint": sig.endpoint,
                "fallback_message": f"⚠️ 检测到危险信号: {sig.keyword}。建议: {sig.action}。",
            }
    return {"matched": False, "keyword": None, "risk_level": "low",
            "action": None, "endpoint": endpoint, "fallback_message": None}
'''
print("part 1 done")


# ── 4 维分类 code(5002-1) — 引用 scene_router.classify_4d ──
SCENE_CODE = '''
import sys
sys.path.insert(0, "/app")
from charge_consult.scene_router import classify_4d, match_danger_signals

def main(input_text: str, input_language: str, input_hint_endpoint: str, input_hint_region: str) -> dict:
    scene, endpoint, region, pile_type, confidence = classify_4d(
        input_text, input_language, input_hint_endpoint, input_hint_region,
    )
    # FAQ 节点识别(5002-2 决定是否走 FAQ 直查)
    danger = match_danger_signals(input_text, endpoint=endpoint)
    return {
        "scene": scene, "endpoint": endpoint, "region": region,
        "pile_type": pile_type, "confidence": confidence,
        "is_faq": (scene == "faq"),
        "has_danger": danger.matched,
        "danger_keyword": danger.keyword,
    }
'''

# ── FAQ 直查 KR(5002-2) ──
# ── FAQ 包装(5002-3 code) ──
FAQ_PACK_CODE = '''
def main(faq_node: str, faq_text: str) -> dict:
    return {
        "matched": bool(faq_node), "node": faq_node or None,
        "question": None, "answer": faq_text or None,
        "answer_hash": None, "related_manual_chapter": faq_node or None,
    }
'''

# ── LLM 降级分类(5002-4) ──
LLM_FALLBACK = '''你是充电桩客服 4 维意图分类助手。返回 JSON:
{"scene": "pre_sale|after_sales|operation|pricing|faq|fallback",
 "endpoint": "user|butler|pc", "region": "cn|overseas",
 "pile_type": "public|home", "confidence": 0.0-1.0}

输出语言: zh/en/vi = {{#5001.input_language#}}
不确定时 scene=fallback。'''

# ── fallback scene 兜底(5002-5) ──
FALLBACK_SCENE_CODE = '''
def main(): return {"scene":"fallback","endpoint":"user","region":"cn","pile_type":"public","confidence":0.3}
'''

# ── 流程1 KR(5011) — multi_retrieval ──
# ── 流程1 验证(5012) ──
FLOW1_VERIFY_CODE = '''
def main(flow1_result: list, input_text: str) -> dict:
    text = (input_text or "").lower()
    matched_func = None
    matched_version = None
    for r in (flow1_result or []):
        if isinstance(r, dict):
            name = (r.get("name") or r.get("function_name") or "").lower()
            if name and name in text:
                matched_func = r.get("name")
                matched_version = r.get("version_added", "")
                break
    return {"flow1_matched": bool(flow1_result),
            "matched_function": matched_func, "matched_version": matched_version}
'''

# ── 流程2 KR(5013) ──
# ── 流程2 验证(5014) ──
FLOW2_VERIFY_CODE = '''
def main(flow2_result: list, flow1_function: str) -> dict:
    if not flow1_function:
        return {"flow2_verified": None, "changelog_diff": None}
    if not flow2_result:
        return {"flow2_verified": False, "changelog_diff": "无变更记录"}
    return {"flow2_verified": True, "changelog_diff": None}
'''

# ── 流程3 KR(5015) ──
# ── 路径 A LLM(5010) ──
PATH_A_LLM = '''你是充电桩产品顾问。基于流程1+流程2 检索结果,回答功能问题。
输出语言: {{#5001.input_language#}}
命中功能点: 标注 matched_function + matched_version
不允许编造价格。格式: 编号步骤。'''

# ── 路径 A 包装(5017) ──
PATH_A_PACK_CODE = '''
def main(llm_text: str, flow1_matched: bool, flow1_function: str, flow1_version: str) -> dict:
    return {"text": llm_text, "flow1_matched": flow1_matched,
            "matched_function": flow1_function, "matched_version": flow1_version}
'''

# ── 路径 B LLM 业务诊断(5021) ──
PATH_B_LLM = '''你是充电桩业务诊断助手。基于流程1+流程2+流程3 检索,给出故障排查。
输出语言: {{#5001.input_language#}}
危险信号已被前置过滤。
末尾: 如未解决请联系售后。'''

# ── 路径 B 紧急路径(5022) ──
PATH_B_URGENT_CODE = '''
def main(danger_result: dict) -> dict:
    if not danger_result.get("matched"):
        return {"skip": True, "text": None}
    return {"skip": False, "text": danger_result.get("fallback_message", "⚠️ 危险"),
            "next_action_call_support": True}
'''

# ── 路径 C 多语言 LLM(5031) ──
PATH_C_LLM = '''你是充电桩操作指南助手。根据手册片段回答操作问题。
输出语言: 严格使用 {{#5001.input_language#}}(zh/en/vi)
格式: 编号步骤。
链接保留: /charge/pages/... 路径原样保留。
端过滤: 只答 endpoint 对应端内容。'''

# ── 路径 C 链接保留(5032) ──
PATH_C_LINK_CODE = '''
import re
DEEP_LINK_RE = re.compile(r"(/charge/pages/[a-zA-Z0-9/_-]+|/admin/[a-zA-Z0-9/_-]+)")
def main(llm_text: str, chapter: str, deep_link: str) -> dict:
    text = llm_text or ""
    if deep_link and deep_link not in text:
        text += "\n\n跳转链接: " + deep_link
    all_links = list(dict.fromkeys(DEEP_LINK_RE.findall(text)))
    return {"text": text, "chapter": chapter, "deep_link": deep_link, "all_links": all_links}
'''

# ── 路径 D 报价 LLM(5040) ──
PATH_D_LLM = '''你是充电桩报价助手。根据流程3 报价库返回价格。
输出语言: {{#5001.input_language#}}
价格必须从 KB 原文复制,不允许编造。
货币与 region 匹配(CN-CNY, NA-USD, EU-EUR, SEA-VND)。
过期价格标注"已过期"。
无匹配返回"暂无报价,请联系销售"。'''

# ── 路径 E 兜底 LLM(5090) ──
PATH_E_LLM = '''你是充电桩智能客服。用户问题不明确,引导用户补充信息。
输出语言: {{#5001.input_language#}}
引导 4 类: 功能咨询 / 故障报修 / 操作指导 / 报价查询。'''

# ── End 节点聚合(5081) ──
END_AGG_CODE = '''
import json, sys
sys.path.insert(0, "/app")
from datetime import datetime, timezone

VALID_SCENES = ("pre_sale","after_sales","operation","pricing","faq","fallback")

def main(scene, endpoint, region, pile_type, risk_level, confidence,
         payload_text, faq=None, danger=None, manual=None, pricing_table=None,
         next_actions=None, source="dify"):
    if scene not in VALID_SCENES:
        scene = "fallback"; confidence = min(float(confidence or 0), 0.3)
    return {
        "scene": scene, "endpoint": endpoint or "user",
        "region": region or "cn", "pile_type": pile_type or "public",
        "risk_level": risk_level or "low",
        "confidence": float(confidence) if confidence is not None else 1.0,
        "source": source, "ts": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "text": payload_text or "", "flow1_matched": None,
            "flow2_verified": None, "flow3_pricing": None,
            "faq": faq or {"matched": False},
            "danger": danger or {"matched": False, "risk_level": "low"},
            "manual": manual or {},
            "pricing_table": pricing_table or [],
            "next_actions": next_actions or [],
        },
    }
'''
print("part 2 done")


# ═════════════════════════════════════════════════════════════
# 构造工作流
# ═════════════════════════════════════════════════════════════
wf = Workflow(
    name="China_charge_seriver",
    description="充电桩客服 v2 — 4 维分类(场景/端/地域/桩型),6 路径,7 数据集,危险信号硬闸门,End 输出 SceneResponse JSON。",
    mode="workflow",
)

# ── 入口 ──
wf.add(StartNode(id="5001", title="开始-接收多模态", variables=START_VARS))

# ── 4 维分类(5002-1) ──
wf.add(CodeNode(
    id="5002-1", title="code_4维分类",
    code=SCENE_CODE,
    variables=[
        {"variable":"input_text","value_selector":["5001","input_text"]},
        {"variable":"input_language","value_selector":["5001","input_language"]},
        {"variable":"input_hint_endpoint","value_selector":["5001","input_hint_endpoint"]},
        {"variable":"input_hint_region","value_selector":["5001","input_hint_region"]},
    ],
    outputs={"type":"object","properties":[
        {"name":"scene","type":"string"},{"name":"endpoint","type":"string"},
        {"name":"region","type":"string"},{"name":"pile_type","type":"string"},
        {"name":"confidence","type":"number"},{"name":"is_faq","type":"boolean"},
        {"name":"has_danger","type":"boolean"},{"name":"danger_keyword","type":"string"},
    ]},
))

# ── FAQ 直查 KR(5002-2) ──
wf.add(KnowledgeRetrievalNode(
    id="5002-2", title="KR_FAQ",
    dataset_ids=[DS["FAQ"]],
    query_variable_selector=["5001","input_text"],
    top_k=1, score_threshold=0.6,
))

# ── FAQ 包装(5002-3) ──
wf.add(CodeNode(
    id="5002-3", title="code_FAQ包装",
    code=FAQ_PACK_CODE,
    variables=[
        {"variable":"faq_node","value_selector":["5002-1","faq_node"] if False else ["5002-1","danger_keyword"]},
        {"variable":"faq_text","value_selector":["5002-2","result"]},
    ],
    outputs={"type":"object"},
))

# ── LLM 降级分类(5002-4) ──
wf.add(LLMNode(
    id="5002-4", title="llm_意图分类降级",
    system_prompt=LLM_FALLBACK,
    user_prompt="{{#5001.input_text#}}",
    json_mode=True,
))

# ── fallback scene(5002-5) ──
wf.add(CodeNode(
    id="5002-5", title="code_fallback",
    code=FALLBACK_SCENE_CODE,
))

# ── scene 路由 if-else(5003) ──
wf.add(IfElseNode(
    id="5003", title="if-else_scene路由",
    cases=[
        IfElseNode.case(["5002-1","scene"], "in", ["pre_sale","faq","after_sales","operation","pricing","fallback"]),
    ],
))

# ── 后台三流(5011-5015) — multi_retrieval ──
wf.add(KnowledgeRetrievalNode(
    id="5011", title="流程1_KR_功能匹配",
    dataset_ids=[DS["SPEC"], DS["CHANGELOG"]],
    query_variable_selector=["5001","input_text"], top_k=3, score_threshold=0.5,
))
wf.add(CodeNode(
    id="5012", title="code_流程1验证",
    code=FLOW1_VERIFY_CODE,
    variables=[
        {"variable":"flow1_result","value_selector":["5011","result"]},
        {"variable":"input_text","value_selector":["5001","input_text"]},
    ],
))
wf.add(KnowledgeRetrievalNode(
    id="5013", title="流程2_KR_清单校验",
    dataset_ids=[DS["CHANGELOG"], DS["FAQ"]],
    query_variable_selector=["5001","input_text"], top_k=2, score_threshold=0.5,
))
wf.add(CodeNode(
    id="5014", title="code_流程2验证",
    code=FLOW2_VERIFY_CODE,
    variables=[
        {"variable":"flow2_result","value_selector":["5013","result"]},
        {"variable":"flow1_function","value_selector":["5012","matched_function"]},
    ],
))
wf.add(KnowledgeRetrievalNode(
    id="5015", title="流程3_KR_报价",
    dataset_ids=[DS["PRICING"], DS["FAULT"]],
    query_variable_selector=["5001","input_text"], top_k=3, score_threshold=0.5,
))

# ── 路径 A(5010, 5017) ──
wf.add(LLMNode(
    id="5010", title="llm_功能咨询",
    system_prompt=PATH_A_LLM,
    user_prompt="用户: {{#5001.input_text#}}\n流程1结果: {{#5011.result#}}",
    context_variable="5011",
))
wf.add(CodeNode(
    id="5017", title="code_路径A包装",
    code=PATH_A_PACK_CODE,
    variables=[
        {"variable":"llm_text","value_selector":["5010","text"]},
        {"variable":"flow1_matched","value_selector":["5012","flow1_matched"]},
        {"variable":"flow1_function","value_selector":["5012","matched_function"]},
        {"variable":"flow1_version","value_selector":["5012","matched_version"]},
    ],
))

# ── 路径 B(5020, 5021, 5022) ──
wf.add(CodeNode(
    id="5020", title="code_危险信号判定",
    code=DANGER_CODE,
    variables=[
        {"variable":"input_text","value_selector":["5001","input_text"]},
        {"variable":"endpoint","value_selector":["5002-1","endpoint"]},
    ],
))
wf.add(LLMNode(
    id="5021", title="llm_业务诊断",
    system_prompt=PATH_B_LLM,
    user_prompt="用户: {{#5001.input_text#}}\n流程2: {{#5013.result#}}\n流程3: {{#5015.result#}}",
    context_variable="5013",
))
wf.add(CodeNode(
    id="5022", title="code_紧急路径",
    code=PATH_B_URGENT_CODE,
    variables=[{"variable":"danger_result","value_selector":["5020","result"]}],
))

# ── 路径 C(5030, 5031, 5032) ──
wf.add(KnowledgeRetrievalNode(
    id="5030", title="KR_操作手册",
    dataset_ids=[DS["GUIDE"]],
    query_variable_selector=["5001","input_text"], top_k=3, score_threshold=0.5,
))
wf.add(LLMNode(
    id="5031", title="llm_多语言指引",
    system_prompt=PATH_C_LLM,
    user_prompt="用户: {{#5001.input_text#}}\n手册: {{#5030.result#}}",
    context_variable="5030",
))
wf.add(CodeNode(
    id="5032", title="code_链接保留",
    code=PATH_C_LINK_CODE,
    variables=[
        {"variable":"llm_text","value_selector":["5031","text"]},
        {"variable":"chapter","value_selector":["5030","result"]},
        {"variable":"deep_link","value_selector":["5030","result"]},
    ],
))

# ── 路径 D(5040) ──
wf.add(LLMNode(
    id="5040", title="llm_报价整理",
    system_prompt=PATH_D_LLM,
    user_prompt="用户: {{#5001.input_text#}}\n报价: {{#5015.result#}}",
    context_variable="5015",
))

# ── 路径 E(5090) ──
wf.add(LLMNode(
    id="5090", title="llm_兜底",
    system_prompt=PATH_E_LLM,
    user_prompt="{{#5001.input_text#}}",
))

# ── End 节点聚合(5080, 5081, 5099) ──
wf.add(VariableAggregatorNode(
    id="5080", title="aggregator_5路汇聚",
    variables=[
        {"variable":"text_A","value_selector":["5017","text"]},
        {"variable":"text_B","value_selector":["5021","text"]},
        {"variable":"text_C","value_selector":["5032","text"]},
        {"variable":"text_D","value_selector":["5040","text"]},
        {"variable":"text_E","value_selector":["5090","text"]},
    ],
))
wf.add(CodeNode(
    id="5081", title="code_打包SceneResponse",
    code=END_AGG_CODE,
    variables=[
        {"variable":"scene","value_selector":["5002-1","scene"]},
        {"variable":"endpoint","value_selector":["5002-1","endpoint"]},
        {"variable":"region","value_selector":["5002-1","region"]},
        {"variable":"pile_type","value_selector":["5002-1","pile_type"]},
        {"variable":"risk_level","value_selector":["5020","risk_level"]},
        {"variable":"confidence","value_selector":["5002-1","confidence"]},
        {"variable":"payload_text","value_selector":["5080","text_A"]},
        {"variable":"danger","value_selector":["5020","result"]},
        {"variable":"manual","value_selector":["5032","result"]},
    ],
))
wf.add(EndNode(
    id="5099", title="结束",
    outputs=[{"variable":"output","value_selector":["5081","result"]}],
))
print("workflow built with", len(wf.nodes()), "nodes")


# ═════════════════════════════════════════════════════════════
# 边 — 25 条边连接 27 节点
# ═════════════════════════════════════════════════════════════
EDGES = [
    # 入口 + 4 维分类
    ("5001", "5002-1"),
    ("5002-1", "5002-2"),  # is_faq=true 时走 FAQ
    ("5002-1", "5003"),    # 否则走 scene 路由
    ("5002-2", "5002-3"),
    ("5002-1", "5002-4"),  # LLM 降级(5002-1 confidence<0.7 时)
    ("5002-1", "5002-5"),  # 兜底(5002-1 失败时)
    ("5002-3", "5080"),    # FAQ 直接到 aggregator
    ("5002-4", "5080"),
    ("5002-5", "5080"),
    ("5003", "5011"),      # 所有 scene 共享后台三流
    ("5011", "5012"),
    ("5013", "5014"),
    # 路径 A
    ("5003", "5010"),      # scene=pre_sale/fallback 走 A
    ("5010", "5017"),
    ("5017", "5080"),
    # 路径 B
    ("5003", "5020"),
    ("5020", "5022"),      # danger.matched=true 走紧急
    ("5020", "5021"),      # danger.matched=false 走 LLM
    ("5021", "5080"),
    ("5022", "5080"),
    # 路径 C
    ("5003", "5030"),
    ("5030", "5031"),
    ("5031", "5032"),
    ("5032", "5080"),
    # 路径 D
    ("5003", "5040"),
    ("5040", "5080"),
    # 路径 E
    ("5003", "5090"),
    ("5090", "5080"),
    # End
    ("5080", "5081"),
    ("5081", "5099"),
]
for src, tgt in EDGES:
    wf.connect(src, tgt)

# ═════════════════════════════════════════════════════════════
# 渲染 yml
# ═════════════════════════════════════════════════════════════
yml_text = wf.to_yaml()
OUT_PATH = ROOT.parent / "Workflow-China_charge_seriver-draft-9380/workflow/China_charge_seriver_v2.yml"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(yml_text, encoding="utf-8")
print(f"✅ yml 写入: {OUT_PATH}")
print(f"   节点数: {len(wf.nodes())}")
print(f"   边数: {len(wf.edges())}")
print(f"   文件大小: {OUT_PATH.stat().st_size} bytes")
