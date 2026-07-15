"""修复骨密度场景屏 3→屏 4 链路断头路。

在 AI_health_consultant_v2.yml 里新增 4 个节点(4104/4105/4110/4111),
把"有 answers 的 report 路径"接到屏 4 方案输出,而不是回到屏 2。

依据 HealthConsultApp.tsx handleSubmitAnswers 的实现:
- res.scene === 'report' 且 payload 包含 solutionRef → 跳屏 4
- 6 种 tag 与 frontend/src/data/solutions.ts BONE_DENSITY_SOLUTIONS 一致
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

YML_PATH = Path(r"D:/AI/company-projects/ai-customer/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/AI_health_consultant_v2.yml")


# 6 种骨密度方案(对齐 frontend/src/data/solutions.ts BONE_DENSITY_SOLUTIONS)
# yml 内联硬编码 — 不调外部资源,保证 workflow 自包含
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


# 节点 4104: 检测 input_answers 是否非空
NODE_4104_CODE = '''
# 4104: 检测答案是否非空,决定走 4010 (LLM 重新分析) 还是 4110 (用答案归类方案)
import json

def main(answers: str) -> dict:
    a = (answers or '').strip()
    if a and a != '{}':
        try:
            obj = json.loads(a)
            if isinstance(obj, dict) and obj:
                return {'has_answers': True}
        except Exception:
            pass
    return {'has_answers': False}
'''.strip()


# 节点 4105: if-else on has_answers
NODE_4105_CONFIG = {
    "cases": [
        {
            "case_id": "true",
            "conditions": [
                {
                    "comparison_operator": "is",
                    "id": "cond-has-answers",
                    "value": True,
                    "varType": "boolean",
                    "variable_selector": ["4104", "has_answers"],
                }
            ],
            "id": "true",
            "logical_operator": "and",
        }
    ],
    "desc": "scene1 内部分流:有 answers → 4110 (用答案生成方案);无 answers → 4010 (LLM 重新分析原报告)",
    "logical_operator": "and",
    "title": "scene1-有答案?",
}


# 节点 4110: 复用 backend/health_consult/questionnaire.py 的 _classify_bone_density 逻辑
NODE_4110_CODE = '''
# 4110: 骨密度答案归类 — 复用 _classify_bone_density (backend/health_consult/questionnaire.py)
# 输入:input_answers(JSON 字符串)
# 输出:tag(方案 key), risk_level
import json

# 骨密度 6 种类型 → 风险等级(对齐 questionnaire.py)
_BONE_DENSITY_RISK = {
    "menopause_related": "medium",
    "vitamin_d_deficient": "medium",
    "calcium_protein_deficient": "low",
    "exercise_deficient": "low",
    "medication_related": "high",
    "fracture_high_risk": "high",
}

# 骨密度 12 题的 tag 分类(对应 questionnaires.ts BONE_DENSITY_QUESTIONNAIRE)
# id -> tag
_QUESTION_TAG = {
    "menopause": "menopause_related",
    "fragility_fracture": "fracture_high_risk",
    "family_osteoporosis": "fracture_high_risk",
    "sun_exposure": "vitamin_d_deficient",
    "calcium_intake": "calcium_protein_deficient",
    "strength_training": "exercise_deficient",
    "low_bmi": "calcium_protein_deficient",
    "steroid_use": "medication_related",
    "smoke_alcohol": "medication_related",
    "chronic_disease": "medication_related",
    "spine_symptom": "fracture_high_risk",
    "vitd_tested": "vitamin_d_deficient",  # 仅 low 时计分
}

# 权重(对齐 questionnaires.ts BONE_DENSITY_QUESTIONNAIRE)
_TRIGGER_ANSWERS = {
    "menopause": {"yes": 3},
    "fragility_fracture": {"yes": 3},
    "family_osteoporosis": {"yes": 2},
    "sun_exposure": {"yes": 2},
    "calcium_intake": {"yes": 2},
    "strength_training": {"yes": 2},
    "low_bmi": {"yes": 1},
    "steroid_use": {"yes": 3},
    "smoke_alcohol": {"yes": 1},
    "chronic_disease": {"yes": 2},
    "spine_symptom": {"yes": 3},
    "vitd_tested": {"low": 2},
}

def main(answers: str) -> dict:
    try:
        a = json.loads(answers) if answers and answers.strip() else {}
    except Exception:
        a = {}
    if not isinstance(a, dict):
        a = {}

    # 按 tag 累加权重
    scores = {}
    for qid, weight_map in _TRIGGER_ANSWERS.items():
        ans = a.get(qid)
        if ans is None:
            continue
        w = weight_map.get(ans, 0)
        if w > 0:
            tag = _QUESTION_TAG.get(qid)
            if tag:
                scores[tag] = scores.get(tag, 0) + w

    if not scores:
        # 无任何风险因素命中 — 兜底为"年龄/绝经相关" (跟 _classify_bone_density 一致)
        return {"tag": "menopause_related", "risk_level": "low"}

    # 硬规则:骨折高风险命中即升级
    if scores.get("fracture_high_risk", 0) >= 3:
        return {"tag": "fracture_high_risk", "risk_level": "high"}

    # 取最高分 tag
    tag = max(scores, key=lambda k: scores[k])
    risk = _BONE_DENSITY_RISK.get(tag, "low")
    return {"tag": tag, "risk_level": risk}
'''.strip()


# 节点 4111: 根据 tag 查 6 种方案,输出 scene1 done payload
NODE_4111_CODE = f'''
# 4111: 根据 tag 组装屏 4 SceneResponse
# 输出结构对齐 frontend handleSubmitAnswers 期望的 ReportDonePayload
# 完整方案内容由前端 getSolution('report', tag) 兜底渲染,这里只传关键字段
import json

SOLUTIONS = {json.dumps(BONE_DENSITY_SOLUTIONS_YML, ensure_ascii=False)}

def main(tag: str, risk_level: str) -> dict:
    sol = SOLUTIONS.get(tag) or SOLUTIONS["menopause_related"]
    payload = {{
        "tag": sol["id"].replace("_v1", ""),  # 前端 getSolution('report', tag) 用裸 tag
        "riskLevel": risk_level,
        "department": sol["department"],
        "oneLineConclusion": sol["oneLineConclusion"],
        "lifestyle": [],  # 前端用本地 fallback 渲染完整内容
        "nutrition": [],
        "alert": [],
        "solutionRef": sol["id"],
    }}
    response = {{
        "scene": "report",
        "risk_level": risk_level,
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

    # 1) 找到 4010/4011/4090/4003/4002/4080 的现有数据,用作新建节点的模板
    by_id = {n["id"]: n for n in nodes}

    # 2) 新增 4 个节点
    new_nodes = [
        # 4104: 检测 has_answers
        {
            "id": "4104",
            "type": "custom",
            "position": {"x": 800, "y": -40},
            "positionAbsolute": {"x": 800, "y": -40},
            "width": 242,
            "height": 90,
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "data": {
                "code": NODE_4104_CODE,
                "code_language": "python3",
                "desc": "检测 input_answers 是否非空 → 路由到 4110 或 4010",
                "outputs": {
                    "has_answers": {"type": "boolean", "children": None},
                },
                "selected": False,
                "title": "scene1_has_answers",
                "type": "code",
                "variables": [
                    {
                        "value_selector": ["4001", "input_answers"],
                        "variable": "answers",
                    }
                ],
            },
        },
        # 4105: if-else on has_answers
        {
            "id": "4105",
            "type": "custom",
            "position": {"x": 800, "y": 40},
            "positionAbsolute": {"x": 800, "y": 40},
            "width": 242,
            "height": 168,
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "data": {
                **NODE_4105_CONFIG,
                "selected": False,
                "type": "if-else",
            },
        },
        # 4110: bone_density_classify
        {
            "id": "4110",
            "type": "custom",
            "position": {"x": 1040, "y": 40},
            "positionAbsolute": {"x": 1040, "y": 40},
            "width": 242,
            "height": 90,
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "data": {
                "code": NODE_4110_CODE,
                "code_language": "python3",
                "desc": "骨密度答案归类 — 按 tag 累加权重,取最高分 tag",
                "outputs": {
                    "tag": {"type": "string", "children": None},
                    "risk_level": {"type": "string", "children": None},
                },
                "selected": False,
                "title": "bone_density_classify",
                "type": "code",
                "variables": [
                    {
                        "value_selector": ["4001", "input_answers"],
                        "variable": "answers",
                    }
                ],
            },
        },
        # 4111: scene1_done_payload
        {
            "id": "4111",
            "type": "custom",
            "position": {"x": 1280, "y": 40},
            "positionAbsolute": {"x": 1280, "y": 40},
            "width": 242,
            "height": 90,
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "data": {
                "code": NODE_4111_CODE,
                "code_language": "python3",
                "desc": "按 tag 查 6 种方案,输出 scene1 done payload(ReportDonePayload)",
                "outputs": {
                    "output": {"type": "string", "children": None},
                },
                "selected": False,
                "title": "scene1_done_payload",
                "type": "code",
                "variables": [
                    {
                        "value_selector": ["4110", "tag"],
                        "variable": "tag",
                    },
                    {
                        "value_selector": ["4110", "risk_level"],
                        "variable": "risk_level",
                    },
                ],
            },
        },
    ]

    # 合并到 nodes(去除已存在的 4104-4111 避免重复)
    existing_ids = {n["id"] for n in nodes}
    for n in new_nodes:
        if n["id"] in existing_ids:
            nodes[:] = [x for x in nodes if x["id"] != n["id"]]
        nodes.append(n)

    # 3) 调整 edges
    edges[:] = [e for e in edges if not (e.get("source") == "4003" and e.get("target") == "4010")]

    new_edges = [
        {
            "data": {
                "isInIteration": False,
                "sourceType": "if-else",
                "targetType": "if-else",
            },
            "id": "edge-4003-4105",
            "source": "4003",
            "sourceHandle": "report",
            "target": "4105",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {
                "isInIteration": False,
                "sourceType": "code",
                "targetType": "code",
            },
            "id": "edge-4002-4104",
            "source": "4002",
            "sourceHandle": "source",
            "target": "4104",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {
                "isInIteration": False,
                "sourceType": "code",
                "targetType": "if-else",
            },
            "id": "edge-4104-4105",
            "source": "4104",
            "sourceHandle": "source",
            "target": "4105",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {
                "isInIteration": False,
                "sourceType": "if-else",
                "targetType": "code",
            },
            "id": "edge-4105-4110",
            "source": "4105",
            "sourceHandle": "true",
            "target": "4110",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {
                "isInIteration": False,
                "sourceType": "if-else",
                "targetType": "llm",
            },
            "id": "edge-4105-4010",
            "source": "4105",
            "sourceHandle": "false",
            "target": "4010",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {
                "isInIteration": False,
                "sourceType": "code",
                "targetType": "code",
            },
            "id": "edge-4110-4111",
            "source": "4110",
            "sourceHandle": "source",
            "target": "4111",
            "targetHandle": "target",
            "type": "custom",
        },
        {
            "data": {
                "isInIteration": False,
                "sourceType": "code",
                "targetType": "variable-aggregator",
            },
            "id": "edge-4111-4090",
            "source": "4111",
            "sourceHandle": "source",
            "target": "4090",
            "targetHandle": "target",
            "type": "custom",
        },
    ]

    new_edge_ids = {e["id"] for e in new_edges}
    edges[:] = [e for e in edges if e.get("id") not in new_edge_ids]
    edges.extend(new_edges)

    # 4) 更新 4090 variable aggregator,把 4111.output 加进去
    for n in nodes:
        if n["id"] == "4090":
            n["data"]["variables"] = [
                ["4011", "output"],
                ["4023", "output"],
                ["4025", "output"],
                ["4032", "output"],
                ["4111", "output"],
            ]
            break

    YML_PATH.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"PATCHED: added 4 nodes (4104/4105/4110/4111), 7 new edges, updated 4090")
    print(f"nodes: {len(nodes)}, edges: {len(edges)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
