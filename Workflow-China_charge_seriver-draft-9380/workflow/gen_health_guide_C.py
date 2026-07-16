# -*- coding: utf-8 -*-
"""生成 C app: 健康严选AI导游 chatflow yml (charge_health_guide_C.yml)
17 节点 advanced-chat, 移植 lkf/app.py 业务逻辑到 Dify.
model: Doubao-Seed-2.0-lite (124 已可用). 预留 deepseek-reasoner 切换(改 model.name).
"""
import json
from ruamel.yaml import YAML

# ---------- 通用配置 ----------
MODEL_DOUBAO = {
    "completion_params": {"max_tokens": 1500, "temperature": 0.6, "top_p": 1},
    "mode": "chat",
    "name": "Doubao-Seed-2.0-lite",
    "provider": "langgenius/volcengine_maas/volcengine_maas",
}
# deepseek-reasoner (用户已配 124 Dify deepseek provider). 不支持vision, 用于纯文本问诊/推荐节点.
MODEL_DEEPSEEK = {
    "completion_params": {"max_tokens": 2000, "temperature": 0.6},
    "mode": "chat",
    "name": "deepseek-reasoner",
    "provider": "langgenius/deepseek/deepseek",
}

VISION_CFG = {"enabled": True, "configs": {"detail": "high", "variable_selector": ["sys", "files"]}}
MEMORY_CFG = {"window": {"enabled": True, "size": 10}}

def node(nid, ntype, title, data_extra, x, y, h=90):
    d = {"title": title, "type": ntype, "selected": False}
    d.update(data_extra)
    return {"data": d, "height": h, "id": nid, "position": {"x": x, "y": y},
            "positionAbsolute": {"x": x, "y": y}, "selected": False,
            "sourcePosition": "right", "targetPosition": "left", "type": "custom", "width": 242}

def edge(src, tgt, src_handle="source", tgt_handle="target", stype="custom", ttype="custom"):
    return {"data": {"sourceType": stype, "targetType": ttype},
            "id": f"e-{src}-{tgt}-{src_handle}", "source": src, "sourceHandle": src_handle,
            "target": tgt, "targetHandle": tgt_handle, "type": "custom"}

# ---------- 节点 ----------
nodes = []

# 7001 Start
nodes.append(node("7001", "start", "Start", {
    "variables": [{
        "default": "", "label": "语言(空=自动)", "options": ["zh", "en", ""],
        "required": False, "type": "select", "variable": "input_language"
    }]
}, -800, 0, h=120))

# 7002 code_准备输入
code_7002 = (
"def main(query: str, input_language: str, files: list) -> dict:\n"
"    text = (query or '').strip()\n"
"    if input_language and input_language.strip():\n"
"        lang = input_language.strip()\n"
"    else:\n"
"        cjk = sum(1 for c in text if '一' <= c <= '鿿')\n"
"        lang = 'zh' if cjk > 0 else 'en'\n"
"    has_file = bool(files) and len(files) > 0\n"
"    return {'query_text': text, 'language': lang, 'has_file': has_file}\n"
)
nodes.append(node("7002", "code", "code_准备输入", {
    "code": code_7002, "code_language": "python3",
    "outputs": {"query_text": {"children": None, "type": "string"},
                "language": {"children": None, "type": "string"},
                "has_file": {"children": None, "type": "boolean"}},
    "variables": [{"value_selector": ["sys", "query"], "variable": "query"},
                  {"value_selector": ["7001", "input_language"], "variable": "input_language"},
                  {"value_selector": ["sys", "files"], "variable": "files"}]
}, -480, 0, h=120))

# 7020 code_算轮次 (输出 is_first/round_stage 供 if-else 用 is 比较, 遵循 B app 模式避免 number 比较操作符)
code_7020 = (
"def main(cv_round: float) -> dict:\n"
"    r = int(cv_round or 0) + 1\n"
"    is_first = (r == 1)\n"
"    stage = 'recommend' if r >= 5 else 'probe'\n"
"    return {'round': r, 'is_first': is_first, 'round_stage': stage}\n"
)
nodes.append(node("7020", "code", "code_算轮次", {
    "code": code_7020, "code_language": "python3",
    "outputs": {"round": {"children": None, "type": "number"},
                "is_first": {"children": None, "type": "boolean"},
                "round_stage": {"children": None, "type": "string"}},
    "variables": [{"value_selector": ["conversation", "cv_round"], "variable": "cv_round"}]
}, -160, 0))

# 7020a assigner_轮次+1
nodes.append(node("7020a", "assigner", "assigner_轮次+1", {
    "items": [{"input_type": "variable", "operation": "over-write",
               "value": ["7020", "round"],
               "variable_selector": ["conversation", "cv_round"]}],
    "version": "2"
}, 120, 0, h=88))

# 7021 if_第1轮 (用 is_first boolean is 比较, B app 验证过的模式)
nodes.append(node("7021", "if-else", "if_第1轮", {
    "cases": [
        {"case_id": "first_round", "logical_operator": "and",
         "conditions": [{"comparison_operator": "is", "id": "c_fr_0", "value": "true",
                         "varType": "boolean", "variable_selector": ["7020", "is_first"]}]},
        {"case_id": "later", "logical_operator": "and",
         "conditions": [{"comparison_operator": "is", "id": "c_lt_0", "value": "false",
                         "varType": "boolean", "variable_selector": ["7020", "is_first"]}]}
    ]
}, 380, 0, h=118))

# 7030 LLM_健康判断 (vision, 输出JSON is_health+summary)
sys_7030 = (
"你判断用户上传的内容是否为健康/医疗/体检相关。看图片(若有)和文本。\n"
"输出严格JSON,不要markdown:\n"
"{\"is_health\": true或false, \"summary\": \"若是健康报告则提取关键指标/异常摘要;若非健康则一句话说明原因\"}\n"
"判定为健康的:体检单/化验单/影像报告/症状描述/健康咨询。非健康:风景照/无关截图/闲聊无健康信息。"
)
nodes.append(node("7030", "llm", "LLM_健康判断", {
    "model": MODEL_DOUBAO,
    "prompt_template": [
        {"id": "sys7030", "role": "system", "text": sys_7030},
        {"id": "user7030", "role": "user",
         "text": "语言:{{#7002.language#}}\n用户输入:{{#7002.query_text#}}\n(若上传了图片请结合图片判断)"}
    ],
    "vision": VISION_CFG, "context": {"enabled": False, "variable_selector": []}
}, 640, -160, h=140))

# 7030b code_解析健康
code_7030b = (
"import json, re\n"
"def main(text: str) -> dict:\n"
"    t = text or ''\n"
"    is_health = False\n"
"    summary = ''\n"
"    m = re.search(r'\\{.*\\}', t, re.DOTALL)\n"
"    if m:\n"
"        try:\n"
"            d = json.loads(m.group(0))\n"
"            is_health = bool(d.get('is_health', False))\n"
"            summary = str(d.get('summary', ''))\n"
"        except Exception:\n"
"            is_health = 'true' in t.lower() and 'false' not in t.lower()\n"
"            summary = t[:200]\n"
"    else:\n"
"        is_health = 'true' in t.lower() and 'false' not in t.lower()\n"
"        summary = t[:200]\n"
"    return {'is_health': is_health, 'report_summary': summary}\n"
)
nodes.append(node("7030b", "code", "code_解析健康", {
    "code": code_7030b, "code_language": "python3",
    "outputs": {"is_health": {"children": None, "type": "boolean"},
                "report_summary": {"children": None, "type": "string"}},
    "variables": [{"value_selector": ["7030", "text"], "variable": "text"}]
}, 920, -160, h=120))

# 7031 if_健康
nodes.append(node("7031", "if-else", "if_健康", {
    "cases": [
        {"case_id": "healthy", "logical_operator": "and",
         "conditions": [{"comparison_operator": "is", "id": "c_h_0", "value": "true",
                         "varType": "boolean", "variable_selector": ["7030b", "is_health"]}]},
        {"case_id": "unhealthy", "logical_operator": "and",
         "conditions": [{"comparison_operator": "is", "id": "c_uh_0", "value": "false",
                         "varType": "boolean", "variable_selector": ["7030b", "is_health"]}]}
    ]
}, 1200, -160, h=118))

# 7032 Answer_委婉拒绝
nodes.append(node("7032", "answer", "Answer_委婉拒绝", {
    "answer": "您上传的内容似乎不包含健康检测相关的信息哦。为了给您专业的建议，请重新上传您的体检/化验报告，或直接描述您的身体感受和症状。",
    "variables": []
}, 1480, -60, h=89))

# 7033 LLM_报告解读问诊 (第1轮, memory, 禁rec)
sys_7033 = (
"# Role\n你是资深、权威且充满人文关怀的「健康管理专家与严选AI导游」,具备全科医生医学常识,善于倾听共情。\n"
"# 本轮任务(第1轮:破冰与报告解读)\n"
"基于用户上传的报告实际内容(或口述症状)提出针对性问题,了解身体感受。通俗解读关键指标/异常。\n"
"# 强制约束\n"
"- 绝对禁止输出商品推荐,JSON块的recommendations字段必须省略,只保留suggestions\n"
"- 不机械索要数据,用关切口吻从常见症状切入\n"
"- 不夸大病情,必要时提醒就医\n"
"- 语言:{{#7002.language#}} (zh=简体中文, en=English)\n"
"# 输出格式\n"
"第一部分:关怀话术+报告解读+提问\n"
"第二部分:最末尾JSON块:\n"
"```json\n{\"suggestions\":[\"快捷回复1\",\"快捷回复2\"],\"warnings\":[\"提醒事项\"],\"metrics\":[{\"name\":\"血清钙\",\"value\":\"2.10 mmol/L\",\"status\":\"偏低\"}]}\n```\n"
"(严禁recommendations字段;status可为正常/偏高/偏低/异常)"
)
nodes.append(node("7033", "llm", "LLM_报告解读问诊", {
    "model": MODEL_DEEPSEEK, "memory": MEMORY_CFG,
    "prompt_template": [
        {"id": "sys7033", "role": "system", "text": sys_7033},
        {"id": "user7033", "role": "user",
         "text": "【健康判断摘要】{{#7030b.report_summary#}}\n【用户输入】{{#7002.query_text#}}"}
    ],
    "context": {"enabled": False, "variable_selector": []}
}, 1480, -220, h=140))

# 7034 Answer_第1轮
nodes.append(node("7034", "answer", "Answer_第1轮", {
    "answer": "{{#7033.text#}}", "variables": [{"value_selector": ["7033", "text"], "variable": "text"}]
}, 1820, -220, h=89))

# 7040 if_到推荐轮 (用 round_stage string is 比较, B app 验证过的模式)
nodes.append(node("7040", "if-else", "if_到推荐轮", {
    "cases": [
        {"case_id": "recommend", "logical_operator": "and",
         "conditions": [{"comparison_operator": "is", "id": "c_r_0", "value": "recommend",
                         "varType": "string", "variable_selector": ["7020", "round_stage"]}]},
        {"case_id": "probe", "logical_operator": "and",
         "conditions": [{"comparison_operator": "is", "id": "c_p_0", "value": "probe",
                         "varType": "string", "variable_selector": ["7020", "round_stage"]}]}
    ]
}, 640, 200, h=118))

# 7041 LLM_问诊 (2-4轮, memory, 禁rec)
sys_7041 = (
"# Role\n你是资深、充满人文关怀的「健康管理专家与严选AI导游」。\n"
"# 本轮任务(第2-4轮:互动分析与根源探究)\n"
"结合前几轮沟通与报告内容,分析病理根源(作息/代谢/免疫等),继续通过问题(饮食/作息/运动)完善用户画像。\n"
"# 强制约束\n"
"- 绝对禁止商品推荐,JSON省略recommendations,只保留suggestions\n"
"- 高情商共情,不机械索要数据\n"
"- 不夸大病情,提醒就医\n"
"- 语言:{{#7002.language#}}\n"
"# 输出格式\n"
"第一部分:根源分析+提问\n"
"第二部分:末尾JSON:\n```json\n{\"suggestions\":[...],\"warnings\":[...],\"metrics\":[...]}\n```\n"
"(严禁recommendations)"
)
nodes.append(node("7041", "llm", "LLM_问诊", {
    "model": MODEL_DEEPSEEK, "memory": MEMORY_CFG,
    "prompt_template": [
        {"id": "sys7041", "role": "system", "text": sys_7041},
        {"id": "user7041", "role": "user", "text": "{{#7002.query_text#}}"}
    ],
    "context": {"enabled": False, "variable_selector": []}
}, 920, 280, h=140))

# 7042 Answer_问诊
nodes.append(node("7042", "answer", "Answer_问诊", {
    "answer": "{{#7041.text#}}", "variables": [{"value_selector": ["7041", "text"], "variable": "text"}]
}, 1260, 280, h=89))

# 7050 KB_商品检索  (dataset_id 占位, 导入后填实际)
nodes.append(node("7050", "knowledge-retrieval", "KB_商品检索", {
    "dataset_ids": ["DATASET_PRODUCT_ID_PLACEHOLDER"],
    "desc": "从健康严选商品库检索与用户需求匹配的商品",
    "multiple_retrieval_config": {
        "reranking_enable": True, "reranking_mode": "reranking_model",
        "reranking_model": {"model": "qwen3-rerank", "provider": "langgenius/tongyi/tongyi"},
        "score_threshold": 0.3, "top_k": 3, "weights": None
    },
    "query_attachment_selector": [], "query_variable_selector": ["7002", "query_text"],
    "retrieval_mode": "multiple"
}, 920, 440, h=134))

# 7051 LLM_推荐 (5轮+, memory, KB context, 出rec)
sys_7051 = (
"# Role\n你是资深「健康管理专家与严选AI导游」。\n"
"# 本轮任务(第5轮及以后:综合总结与严选推荐)\n"
"对用户健康状况做综合性总结,并从下方知识库检索结果中精准匹配推荐最适合的商品。\n"
"# 强制约束\n"
"- 只推荐【知识库检索结果】中的真实商品,绝不编造商品ID\n"
"- 没有合适商品则委婉告知\n"
"- 不夸大病情,提醒就医\n"
"- 语言:{{#7002.language#}}\n"
"# 输出格式\n"
"第一部分:健康综合总结+商品推荐理由\n"
"第二部分:末尾JSON:\n```json\n{\"recommendations\":[{\"product_id\":\"商品ID\",\"reason\":\"匹配理由\"}],\"suggestions\":[...],\"warnings\":[...]}\n```\n"
"(product_id必须来自知识库检索结果)"
)
nodes.append(node("7051", "llm", "LLM_推荐", {
    "model": MODEL_DEEPSEEK, "memory": MEMORY_CFG,
    "prompt_template": [
        {"id": "sys7051", "role": "system", "text": sys_7051},
        {"id": "user7051", "role": "user", "text": "【用户输入】{{#7002.query_text#}}\n\n请结合知识库检索结果为我推荐。"}
    ],
    "context": {"enabled": True, "variable_selector": ["7050", "result"]},
    "vision": {"enabled": False, "configs": {"detail": "low", "variable_selector": ["sys", "files"]}}
}, 1260, 440, h=140))

# 7052 Answer_推荐
nodes.append(node("7052", "answer", "Answer_推荐", {
    "answer": "{{#7051.text#}}", "variables": [{"value_selector": ["7051", "text"], "variable": "text"}]
}, 1600, 440, h=89))

# ---------- 边 ----------
edges = [
    edge("7001", "7002", stype="start", ttype="code"),
    edge("7002", "7020", stype="code", ttype="code"),
    edge("7020", "7020a", stype="code", ttype="assigner"),
    edge("7020a", "7021", stype="assigner", ttype="if-else"),
    # 第1轮分支
    edge("7021", "7030", src_handle="first_round", stype="if-else", ttype="llm"),
    edge("7030", "7030b", stype="llm", ttype="code"),
    edge("7030b", "7031", stype="code", ttype="if-else"),
    edge("7031", "7033", src_handle="healthy", stype="if-else", ttype="llm"),
    edge("7031", "7032", src_handle="unhealthy", stype="if-else", ttype="answer"),
    edge("7033", "7034", stype="llm", ttype="answer"),
    # 非第1轮分支
    edge("7021", "7040", src_handle="later", stype="if-else", ttype="if-else"),
    edge("7040", "7041", src_handle="probe", stype="if-else", ttype="llm"),
    edge("7041", "7042", stype="llm", ttype="answer"),
    edge("7040", "7050", src_handle="recommend", stype="if-else", ttype="knowledge-retrieval"),
    edge("7050", "7051", stype="knowledge-retrieval", ttype="llm"),
    edge("7051", "7052", stype="llm", ttype="answer"),
]

# ---------- 组装 ----------
doc = {
    "app": {
        "description": "App C: 健康严选AI导游(体检报告识别+多轮问诊+5轮延迟商品推荐). model=Doubao-Seed-2.0-lite, 预留deepseek-reasoner切换(改model.name)",
        "icon": "🩺", "icon_background": "#E0F0FF", "icon_type": "emoji",
        "mode": "advanced-chat", "name": "health_yanxuan_guide_C",
        "use_icon_as_answer_icon": False
    },
    "dependencies": [
        {"current_identifier": None, "type": "marketplace",
         "value": {"marketplace_plugin_unique_identifier": "langgenius/volcengine_maas:0.0.51@10500d8c8e350242a0db2dda11c276685ab947ec0b41f9b94ea73c2919aacab7", "version": None}},
        {"current_identifier": None, "type": "marketplace",
         "value": {"marketplace_plugin_unique_identifier": "langgenius/tongyi:0.2.0@4e5891a2f4fff19b005a662a1fadff0e56b62b2dd1b4a93bdffae83c5b38b05e", "version": None}},
    ],
    "kind": "app", "version": "0.6.0",
    "workflow": {
        "conversation_variables": [
            {"id": "c7000-0001-4000-8000-000000000001", "name": "cv_round",
             "value": 0, "value_type": "number",
             "description": "对话轮次计数(0起始,每轮+1,>=5触发商品推荐分支)"}
        ],
        "environment_variables": [],
        "features": {
            "file_upload": {
                "enabled": True,
                "allowed_file_types": ["image", "document"],
                "allowed_file_extensions": ["JPG", "PNG", "JPEG", "WEBP", "PDF", "DOCX"],
                "allowed_file_upload_methods": ["remote_url", "local_file"],
                "fileUploadConfig": {"file_size_limit": 15, "image_file_size_limit": 10,
                                     "file_upload_limit": 20, "image_file_batch_limit": 10,
                                     "batch_count_limit": 5, "audio_file_size_limit": 50,
                                     "video_file_size_limit": 100, "workflow_file_upload_limit": 10,
                                     "attachment_image_file_size_limit": 2, "single_chunk_attachment_limit": 10},
                "image": {"enabled": True, "number_limits": 3, "transfer_methods": ["local_file", "remote_url"]}
            },
            "opening_statement": "您好!我是您的健康严选AI导游。您可以输入健康疑问,或上传体检/化验报告,我将为您解读并给出专业建议。",
            "suggested_questions": [],
            "speech_to_text": {"enabled": False},
            "text_to_speech": {"enabled": False},
            "retriever_resource": {"enabled": True},
            "sensitive_word_avoidance": {"enabled": False}
        },
        "graph": {"edges": edges, "nodes": nodes,
                  "viewport": {"x": 0, "y": 0, "zoom": 0.5, "maxZoom": 1, "minZoom": 0.2}},
        "rag_pipeline_variables": []
    }
}

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.preserve_quotes = True
yaml.width = 4096
out = "charge_health_guide_C.yml"
with open(out, "w", encoding="utf-8") as f:
    yaml.dump(doc, f)
print(f"生成 {out}: {len(nodes)} 节点, {len(edges)} 边")
