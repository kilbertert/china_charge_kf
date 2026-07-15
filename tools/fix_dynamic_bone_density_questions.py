"""骨密度场景改 LLM 动态生成 3-5 个上下文相关的跟进问题 + LLM 答案分类。

背景:用户反馈骨密度 12 题甄别表第一题永远是"是否绝经",对男性/年轻/儿童用户不友好。
     改为由 LLM 根据报告数据生成 3-5 个上下文相关的跟进问题(会跳过 menopause 如果
     T值没有骨质疏松迹象、用户明显是男性等),答案也由 LLM 分类。

变更:
  1. 4010 prompt 增加 `followUpQuestions` 输出
  2. 4011 code 提取 followUpQuestions 放到 payload.questions
  3. 删除 4110/4111(基于 ID 硬编码的规则分类器)
  4. 新增 4120 (LLM):根据 answers + metrics 分类成 6 个 tag 之一
  5. 新增 4121 (code):根据 tag 查 6 种方案(复用原 4111 的字典)
  6. 路由:4105 (true) → 4120 → 4121 → 4090
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

YML_PATH = Path(r"D:/AI/company-projects/ai-customer/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/AI_health_consultant_v2.yml")


# 6 种骨密度方案(对齐 frontend/src/data/solutions.ts BONE_DENSITY_SOLUTIONS)
BONE_DENSITY_SOLUTIONS_YML = {
    "menopause_related": {
        "id": "menopause_related_v1",
        "title": "年龄/绝经相关骨量流失型",
        "riskLevel": "medium",
        "department": "内分泌科 / 骨质疏松门诊",
        "oneLineConclusion": "您的骨量下降与年龄和绝经后激素变化相关,需要专业评估和系统管理。",
    },
    "vitamin_d_deficient": {
        "id": "vitamin_d_deficient_v1",
        "title": "维生素D不足/日晒不足型",
        "riskLevel": "medium",
        "department": "内分泌科",
        "oneLineConclusion": "您的骨量下降与维生素 D 不足高度相关,补 D 是当下最直接可做的事。",
    },
    "calcium_protein_deficient": {
        "id": "calcium_protein_deficient_v1",
        "title": "钙和蛋白摄入不足型",
        "riskLevel": "low",
        "department": "营养科 / 骨质疏松门诊",
        "oneLineConclusion": "您的骨量下降与饮食结构有关,先从调整餐盘开始,效果安全可预期。",
    },
    "exercise_deficient": {
        "id": "exercise_deficient_v1",
        "title": "缺乏运动/肌力不足型",
        "riskLevel": "low",
        "department": "康复科 / 骨质疏松门诊",
        "oneLineConclusion": "您的骨量下降与长期缺乏运动相关,合适的负重训练能有效逆转趋势。",
    },
    "medication_related": {
        "id": "medication_related_v1",
        "title": "药物或慢病相关型",
        "riskLevel": "high",
        "department": "内分泌科 / 相关慢病专科",
        "oneLineConclusion": "您的骨量下降与长期用药或慢性病相关,需要专科医生综合评估治疗方案。",
    },
    "fracture_high_risk": {
        "id": "fracture_high_risk_v1",
        "title": "骨折高风险型",
        "riskLevel": "high",
        "department": "骨科 / 骨质疏松门诊",
        "oneLineConclusion": "您存在多项骨折高风险因素,需要尽快评估是否启动抗骨松药物治疗。",
    },
}


# 4010 prompt 追加(在原 schema 后面)
PROMPT_4010_ADDITION = '''

# 跟进问题生成(场景一专属!)
基于已识别的 metrics(且 confidence=high),生成 3-5 个对客户最有帮助的跟进问题,
用来判断客户骨量下降的原因。**这些问题必须 100% 上下文相关,不能套用固定模板。**

## 规则
- **第一题必须是关于年龄/性别**(通用筛选)。不是 menopause。
- **跳过 menopause 问题** 当以下任一条件满足:
  - 客户输入文本中明确显示是男性(如"我老公""我爸""我儿子")
  - 客户年龄明确< 40(从报告头/客户文本可推断)
  - T 值全部正常(> -1.0),不需要问激素相关
- **跳过已通过 metrics 知道的信息**:
  - 报告里已有 25-OH 维生素 D → 不问"您有检查过维生素 D 吗?"
  - 报告里 T 值都在 -1.0 以上 → 可以问更开放的问题,如饮食/运动
- **不要问客户没数据能回答的问题**(如"您的具体 T 值是多少"——metrics 已经有了)
- **避免堆叠陷阱**:不要连续问 3 个 yes/no,每题给 2-4 个选项

## 输出 schema(追加)
{
  "followUpQuestions": [
    { "id": "q1", "text": "您的年龄段是?", "options": [{"key": "u40", "label": "40 岁以下"}, {"key": "40_50", "label": "40-50 岁"}, {"key": "50_60", "label": "50-60 岁"}, {"key": "o60", "label": "60 岁以上"}] },
    { "id": "q2", "text": "您的性别是?", "options": [{"key": "male", "label": "男"}, {"key": "female", "label": "女"}, {"key": "na", "label": "不便透露"}] }
  ]
}

**只输出 JSON,不要 markdown 包裹、不要解释文字。followUpQuestions 必须有 3-5 项,严格按上面规则生成。**'''


# 4011 code 替换(把 followUpQuestions 放进 payload.questions,删 questionnaireRef)
NODE_4011_CODE = '''
# 解析 LLM 输出 + 严格无硬编码兜底 + 硬验证防捏造
# 修改:把 LLM 生成的 followUpQuestions 放进 payload.questions
# 修改:不再依赖 frontend/src/data/questionnaires.ts 硬编码 12 题
import json
import re


# DXA 相关指标的合法名称关键词 — 缺一不可通过
ALLOWED_METRIC_KEYWORDS = ("T值", "T 值", "T-score", "T score", "Z值", "Z 值", "Z-score", "25-OH", "维生素D", "维生素 D", "血钙", "BMD", "骨密度")

# T 值的医学合理范围 — 超出即视为 LLM 捏造
T_VALUE_MIN = -10.0
T_VALUE_MAX = 5.0

# problemPriority 白名单 — 防止 LLM 虚构风险方向
ALLOWED_PP_NAMES = frozenset({
    "骨密度下降", "骨量减少", "骨质疏松", "维生素D不足", "血钙异常",
    "T值偏低", "T值异常", "腰椎骨密度下降", "股骨颈骨密度下降", "全髋骨密度下降",
})


def _parse_llm_json(llm_text):
    text = (llm_text or "").strip()
    if not text:
        return {}
    try:
        if text.startswith("{"):
            return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\\{.*\\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}


def _grade_t(t):
    try:
        v = float(t)
    except Exception:
        return "unknown"
    if v >= -1.0:
        return "normal"
    if v > -2.5:
        return "bone_loss"
    return "osteoporosis"


def _is_valid_metric_name(name):
    if not name or not isinstance(name, str):
        return False
    return any(kw in name for kw in ALLOWED_METRIC_KEYWORDS)


def _is_valid_t_value(v):
    try:
        f = float(v)
    except Exception:
        return False
    return T_VALUE_MIN <= f <= T_VALUE_MAX


def _sanitize_questions(raw_questions):
    """过滤 LLM 生成的 followUpQuestions,确保至少有 3 个、每题有 options。"""
    if not isinstance(raw_questions, list):
        return None
    out = []
    seen_ids = set()
    for q in raw_questions:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id", "")).strip()
        text = str(q.get("text", "")).strip()
        options = q.get("options", [])
        if not qid or not text or not isinstance(options, list) or len(options) < 2:
            continue
        clean_options = []
        seen_keys = set()
        for opt in options:
            if not isinstance(opt, dict):
                continue
            k = str(opt.get("key", "")).strip()
            label = str(opt.get("label", "")).strip()
            if not k or not label or k in seen_keys:
                continue
            seen_keys.add(k)
            clean_options.append({"key": k, "label": label})
        if len(clean_options) < 2:
            continue
        if qid in seen_ids:
            continue
        seen_ids.add(qid)
        out.append({"id": qid, "text": text, "options": clean_options})
        if len(out) >= 5:
            break
    return out if len(out) >= 3 else None


def main(llm_text):
    data = _parse_llm_json(llm_text)
    raw_metrics = data.get("metrics") or []

    # 硬验证 0: confidence gate
    confidence = str(data.get("confidence", "")).lower().strip()
    llm_data_complete = bool(data.get("dataComplete", False))
    if llm_data_complete and confidence != "high":
        return _insufficient("fabrication_detected", "AI 在解析过程中无法确认报告内容,请重新上传清晰的 DXA 报告或直接粘贴 T 值(如 '腰椎 L1-L4 T值 -2.1')。")

    # 硬验证 1 + 2: 指标和 T 值范围
    metrics = [m for m in raw_metrics if _is_valid_metric_name(m.get("name", ""))]
    t_values = []
    for m in metrics:
        name = m.get("name", "")
        if "T" in name or "t" in name:
            v = m.get("value")
            if _is_valid_t_value(v):
                t_values.append(float(v))

    has_real_data = bool(t_values)
    if not has_real_data:
        return _insufficient("no_metrics_extracted", "未识别到有效的骨密度数据。请您:(1) 上传清晰的 DXA 报告图片,或 (2) 直接粘贴报告中的 T 值(如 '腰椎 L1-L4 T值 -2.1')。")

    # T 值分级
    for m in metrics:
        name = m.get("name", "")
        m["level"] = _grade_t(m.get("value")) if ("T" in name or "t" in name) else "unknown"

    yours_t = min(t_values)
    levels = [m.get("level", "unknown") for m in metrics]
    if "osteoporosis" in levels:
        risk_level = "high"
    elif "bone_loss" in levels:
        risk_level = "medium"
    elif "normal" in levels:
        risk_level = "low"
    else:
        risk_level = "low"

    counts = {"normal": 0, "bone_loss": 0, "osteoporosis": 0, "unknown": 0}
    for lv in levels:
        counts[lv if lv in counts else "unknown"] += 1
    total = sum(counts.values()) or 1
    risk_distribution = []
    if counts["osteoporosis"] > 0:
        risk_distribution.append({"name": "骨质疏松风险", "value": round(100 * counts["osteoporosis"] / total)})
    if counts["bone_loss"] > 0:
        risk_distribution.append({"name": "骨量减少", "value": round(100 * counts["bone_loss"] / total)})
    if counts["normal"] > 0:
        risk_distribution.append({"name": "正常", "value": round(100 * counts["normal"] / total)})

    one_line = data.get("oneLineConclusion", "").strip()
    if not one_line:
        one_line = "本次初筛结果仅供参考,具体诊断请咨询专业医师。"

    # problemPriority 白名单
    problem_priority = data.get("problemPriority") or []
    if problem_priority:
        filtered_pp = [p for p in problem_priority if p.get("name") in ALLOWED_PP_NAMES]
        if len(filtered_pp) != len(problem_priority):
            problem_priority = []

    # ★ 新增:提取 LLM 动态生成的 followUpQuestions
    follow_up = _sanitize_questions(data.get("followUpQuestions"))
    if follow_up is None:
        # LLM 没生成或生成了无效的 — 兜底:用一个最小通用问卷(3 题,无 menopause 偏置)
        follow_up = [
            {"id": "q_age", "text": "您的年龄段是?", "options": [
                {"key": "u40", "label": "40 岁以下"},
                {"key": "40_50", "label": "40-50 岁"},
                {"key": "50_60", "label": "50-60 岁"},
                {"key": "o60", "label": "60 岁以上"},
            ]},
            {"id": "q_lifestyle", "text": "您平时有规律的运动或日晒吗?", "options": [
                {"key": "both", "label": "都有"},
                {"key": "exercise", "label": "只运动,日晒少"},
                {"key": "sun", "label": "只日晒,运动少"},
                {"key": "neither", "label": "都少"},
            ]},
            {"id": "q_history", "text": "您是否长期服用激素类药物,或有过轻微摔倒后骨折?", "options": [
                {"key": "steroid", "label": "服用激素"},
                {"key": "fracture", "label": "有过骨折"},
                {"key": "both", "label": "两者都有"},
                {"key": "neither", "label": "都没有"},
            ]},
        ]

    payload = {
        "reportType": "bone_density",
        "dataComplete": True,
        "metrics": metrics,
        "tValueChart": {
            "normal": -1.0,
            "yours": yours_t,
            "thresholds": {"normal": -1.0, "loss": -2.5},
        },
        "riskDistribution": risk_distribution,
        "oneLineConclusion": one_line,
        "problemPriority": problem_priority,
        "questions": follow_up,  # ★ 新增:替代 hardcoded 12 题
    }
    response = {
        "scene": "report",
        "risk_level": risk_level,
        "scene_confidence": 0.85,
        "payloadKind": "complete",
        "payload": payload,
    }
    return {"output": json.dumps(response, ensure_ascii=False)}


def _insufficient(reason, user_message):
    payload = {
        "reportType": "bone_density",
        "dataComplete": False,
        "reason": reason,
        "userMessage": user_message,
        "metrics": [],
        "problemPriority": [],
    }
    response = {
        "scene": "report",
        "risk_level": "low",
        "scene_confidence": 0.3,
        "payloadKind": "insufficient_data",
        "payload": payload,
    }
    return {"output": json.dumps(response, ensure_ascii=False)}
'''.strip()


# 4120 (LLM):根据 metrics + 答案分类成 6 个 tag 之一
NODE_4120_PROMPT = '''你是销售小程序 AI 健康初筛助手的骨密度答案分类器。

# 输入
- 已识别的骨密度指标(从 LLM 提取的报告数据)
- 客户的甄别表答案
- 6 种可能的分类(必须选一个):
  1. menopause_related — 年龄/绝经相关
  2. vitamin_d_deficient — 维生素 D 不足/日晒不足
  3. calcium_protein_deficient — 钙和蛋白摄入不足
  4. exercise_deficient — 缺乏运动/肌力不足
  5. medication_related — 药物或慢病相关
  6. fracture_high_risk — 骨折高风险

# 你的任务
综合客户报告数据 + 甄别表答案,判断最可能的骨量下降原因。

# 风险等级
- high: 骨折高风险(有过摔倒骨折/多处风险因素命中) 或 长期激素用药
- medium: 绝经相关/维生素 D 不足/中度风险
- low: 仅生活方式(运动少/饮食不足) 单因素

# 关键判断规则
- 客户回答里明确选了"有过骨折"或"激素" → 大概率 medication_related 或 fracture_high_risk
- 客户年龄段 > 50 + T值在骨质疏松范围 + 性别女 → menopause_related (但客户没明确说是否绝经时,根据年龄推断)
- 客户回答里选了"日晒少"或"运动少" → 优先 vitamin_d_deficient / exercise_deficient
- 不要因为问了某个问题就把它对应的分类当成结果 — 看整体

# 必须以 JSON 输出(只输出 JSON,不要 markdown 包裹、不要解释文字)
{
  "tag": "menopause_related" | "vitamin_d_deficient" | "calcium_protein_deficient" | "exercise_deficient" | "medication_related" | "fracture_high_risk",
  "risk_level": "low" | "medium" | "high",
  "reasoning": "一两句话说明为什么这么分类"
}'''


# 4121 (code):根据 tag 查 6 种方案
NODE_4121_CODE = f'''
# 4121: 根据 4120 LLM 分类的 tag,查 6 种方案并输出 ReportDonePayload
# 完整 lifestyle/nutrition/alert 由前端 getSolution('report', tag) 兜底渲染
import json

SOLUTIONS = {json.dumps(BONE_DENSITY_SOLUTIONS_YML, ensure_ascii=False)}
ALLOWED_TAGS = frozenset(SOLUTIONS.keys())

def main(classify_text):
    try:
        cls = json.loads(classify_text) if classify_text else {{}}
    except Exception:
        cls = {{}}
    if not isinstance(cls, dict):
        cls = {{}}

    tag = str(cls.get("tag", "")).strip()
    if tag not in ALLOWED_TAGS:
        # LLM 输出无效,兜底为低风险运动不足(最保守)
        tag = "exercise_deficient"

    risk = str(cls.get("risk_level", "")).strip().lower()
    if risk not in ("low", "medium", "high", "urgent"):
        # 用 SOLUTIONS 里的默认值
        risk = SOLUTIONS[tag]["riskLevel"]

    sol = SOLUTIONS[tag]
    payload = {{
        "tag": tag,
        "riskLevel": risk,
        "department": sol["department"],
        "oneLineConclusion": sol["oneLineConclusion"],
        "lifestyle": [],
        "nutrition": [],
        "alert": [],
        "solutionRef": sol["id"],
    }}
    response = {{
        "scene": "report",
        "risk_level": risk,
        "scene_confidence": 0.9,
        "payloadKind": "report_done",
        "payload": payload,
    }}
    return {{"output": json.dumps(response, ensure_ascii=False)}}
'''.strip()


def main() -> int:
    raw = yaml.safe_load(YML_PATH.read_text(encoding="utf-8"))
    graph = raw["workflow"]["graph"]
    nodes = graph["nodes"]
    edges = graph["edges"]

    # 1) 找到 4010,把 prompt 追加 followUpQuestions 部分
    for n in nodes:
        if n["id"] == "4010":
            prompt_list = n["data"]["prompt_template"]
            for item in prompt_list:
                if item.get("role") == "system":
                    item["text"] = item.get("text", "") + PROMPT_4010_ADDITION
                    break
            break

    # 2) 找到 4011,替换 code 字段
    for n in nodes:
        if n["id"] == "4011":
            n["data"]["code"] = NODE_4011_CODE
            n["data"]["desc"] = "校验 LLM JSON 输出 + 提取 followUpQuestions 放进 payload.questions(替代 hardcoded 12 题)"
            break

    # 3) 删除 4110, 4111 (硬编码规则分类器)
    nodes[:] = [n for n in nodes if n["id"] not in ("4110", "4111")]

    # 4) 删除所有引用 4110/4111 的 edges
    edges[:] = [e for e in edges if e.get("source") not in ("4110", "4111") and e.get("target") not in ("4110", "4111")]

    # 5) 新增 4120 (LLM) 和 4121 (code)
    new_nodes = [
        {
            "id": "4120",
            "type": "custom",
            "position": {"x": 1040, "y": 40},
            "positionAbsolute": {"x": 1040, "y": 40},
            "width": 242,
            "height": 132,
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "data": {
                "context": {"enabled": False, "variable_selector": []},
                "desc": "LLM 分类:根据 metrics + answers 输出 6 种 tag 之一",
                "model": {
                    "completion_params": {"max_tokens": 512, "temperature": 0.1, "top_p": 1},
                    "mode": "chat",
                    "name": "Doubao-Seed-2.0-lite",
                    "provider": "langgenius/volcengine_maas/volcengine_maas",
                },
                "prompt_template": [
                    {"id": "sys-cls", "role": "system", "text": NODE_4120_PROMPT},
                    {
                        "id": "user-cls",
                        "role": "user",
                        "text": (
                            "客户报告数据(metrics): {{#4011.output#}}\n\n"
                            "客户甄别表答案(answers): {{#4001.input_answers#}}"
                        ),
                    },
                ],
                "selected": False,
                "title": "scene1_LLM_答案分类",
                "type": "llm",
                "vision": {"enabled": False},
            },
        },
        {
            "id": "4121",
            "type": "custom",
            "position": {"x": 1280, "y": 40},
            "positionAbsolute": {"x": 1280, "y": 40},
            "width": 242,
            "height": 90,
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "data": {
                "code": NODE_4121_CODE,
                "code_language": "python3",
                "desc": "按 4120 LLM 分类的 tag 查 6 种方案,输出 ReportDonePayload",
                "outputs": {"output": {"type": "string", "children": None}},
                "selected": False,
                "title": "scene1_done_payload",
                "type": "code",
                "variables": [
                    {"value_selector": ["4120", "text"], "variable": "classify_text"},
                ],
            },
        },
    ]
    for n in new_nodes:
        if n["id"] in {x["id"] for x in nodes}:
            nodes[:] = [x for x in nodes if x["id"] != n["id"]]
        nodes.append(n)

    # 6) 新增 edges
    new_edges = [
        {
            "data": {"isInIteration": False, "sourceType": "if-else", "targetType": "llm"},
            "id": "edge-4105-4120",
            "source": "4105",
            "sourceHandle": "true",
            "target": "4120",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {"isInIteration": False, "sourceType": "llm", "targetType": "code"},
            "id": "edge-4120-4121",
            "source": "4120",
            "sourceHandle": "source",
            "target": "4121",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {"isInIteration": False, "sourceType": "code", "targetType": "variable-aggregator"},
            "id": "edge-4121-4090",
            "source": "4121",
            "sourceHandle": "source",
            "target": "4090",
            "targetHandle": "target",
            "type": "custom",
        },
    ]
    new_edge_ids = {e["id"] for e in new_edges}
    edges[:] = [e for e in edges if e.get("id") not in new_edge_ids]
    edges.extend(new_edges)

    # 7) 更新 4090 variable aggregator:把 4121.output 加进去(4111.output 已被替换)
    for n in nodes:
        if n["id"] == "4090":
            n["data"]["variables"] = [
                ["4011", "output"],
                ["4023", "output"],
                ["4025", "output"],
                ["4032", "output"],
                ["4121", "output"],
            ]
            break

    YML_PATH.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"PATCHED: 4010 prompt +followUpQuestions, 4011 code replaced, 4110/4111 removed, 4120/4121 added")
    print(f"nodes: {len(nodes)}, edges: {len(edges)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
