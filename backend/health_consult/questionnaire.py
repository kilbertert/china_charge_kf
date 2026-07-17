"""量表定义 + 答案归类逻辑。

本模块是 `frontend/src/data/questionnaires.ts` 的 Python 等价镜像,
字段结构与 TS 版本严格一致,后端用于本地兜底(在 Dify 失败或前端直连时使用)。

数据来源:AI健康咨询模块场景GPT对话1.docx
  - 骨密度 12 题(P454-465)
  - 腿疼危险信号 7 题(P551-581)
  - 腿疼定位 4 题(P613-650)
  - 腿疼病史 3 题(P1336-1348)
"""

from __future__ import annotations

from typing import Optional, TypedDict

from .compliance_loader import get_config


class QuestionOption(TypedDict):
    key: str
    label: str
    weight: int


class Question(TypedDict):
    id: str
    text: str
    type: str  # "single" | "multi"
    options: list[QuestionOption]
    tag: str


class Questionnaire(TypedDict):
    id: str
    scene: str  # "report" | "symptom" | "product"
    title: str
    description: str
    questions: list[Question]


# ─── 量表 (单一事实源 shared/compliance.yaml) ──────────────────
_cfg = get_config()

BONE_DENSITY_QUESTIONNAIRE: Questionnaire = _cfg.get_questionnaire("bone_density_v1")  # type: ignore[assignment]
LEG_PAIN_QUESTIONNAIRE: Questionnaire = _cfg.get_questionnaire("leg_pain_v1")  # type: ignore[assignment]

ALL_QUESTIONNAIRES: list[Questionnaire] = [
    BONE_DENSITY_QUESTIONNAIRE,
    LEG_PAIN_QUESTIONNAIRE,
]



def get_questionnaire(questionnaire_id: str) -> Optional[Questionnaire]:
    """按 id 查询量表。"""
    for q in ALL_QUESTIONNAIRES:
        if q["id"] == questionnaire_id:
            return q
    return None


def list_questionnaires() -> list[Questionnaire]:
    """返回所有量表。"""
    return list(ALL_QUESTIONNAIRES)


# ─── 答案归类逻辑 ──────────────────────────────────────────────

# 骨密度 6 种类型 → 风险等级
_BONE_DENSITY_RISK = _cfg.tag_risk_map("bone_density")
# 注: leg_pain 分类函数硬编码 tag+risk (6 条规则按优先级), _LEG_PAIN_RISK 死表已删


def _calc_tag_scores(questions: list[Question], answers: dict[str, str]) -> dict[str, int]:
    """按 question.tag 累加被选项的 weight。"""
    scores: dict[str, int] = {}
    for q in questions:
        ans = answers.get(q["id"])
        if ans is None:
            continue
        for opt in q["options"]:
            if opt["key"] == ans:
                scores[q["tag"]] = scores.get(q["tag"], 0) + opt["weight"]
                break
    return scores


def _classify_bone_density(answers: dict[str, str]) -> tuple[str, str, str]:
    """骨密度答案归类:按 tag 权重计算,选最高分;若 fracture 命中即升级。"""
    scores = _calc_tag_scores(BONE_DENSITY_QUESTIONNAIRE["questions"], answers)
    if not scores:
        return ("report", "menopause_related", "low")
    # 高风险 tag 命中即升级为 fracture_high_risk
    if scores.get("fracture_high_risk", 0) >= _cfg.threshold("bone_density", "fracture_high_risk_min_weight", 3):
        return ("report", "fracture_high_risk", "high")
    tag = max(scores, key=lambda k: scores[k])
    risk = _BONE_DENSITY_RISK.get(tag, "low")
    return ("report", tag, risk)


def _classify_leg_pain(answers: dict[str, str]) -> tuple[str, str, str]:
    """腿疼答案归类:
    - A 表(危险信号)任一命中配置阈值(当前 weight>=2) → urgent
    - 否则按 B+C 表答案匹配 6 种类型
    """
    urgent_questions = [q for q in LEG_PAIN_QUESTIONNAIRE["questions"] if q["tag"] == "urgent"]
    for q in urgent_questions:
        ans = answers.get(q["id"])
        if ans is None:
            continue
        for opt in q["options"]:
            if opt["key"] == ans and opt["weight"] >= _cfg.threshold("leg_pain", "urgent_min_weight", 2):
                return ("symptom", "vascular_risk", "urgent")

    location = answers.get("location", "")
    trigger = answers.get("trigger", "")
    quality = answers.get("quality", "")
    side = answers.get("side", "")
    past = answers.get("past_history", "")
    lab = answers.get("lab_abnormal", "")

    # 规则 1: 腰椎病史 + 麻痛/刺痛 + 久坐后 → 腰椎神经
    if (past == "yes" and quality in ("numb", "stabbing") and trigger == "after_sit_stand"):
        return ("symptom", "lumbar_radiculopathy", "medium")
    if quality == "radiating" or (quality == "numb" and location == "radiating"):
        return ("symptom", "lumbar_radiculopathy", "medium")

    # 规则 2: 膝盖 + 上下楼 + 久坐后 → 膝关节退变
    if location == "knee" and trigger in ("stairs", "after_sit_stand"):
        return ("symptom", "knee_degeneration", "medium")

    # 规则 3: 尿酸/痛风炎症(体检异常 + 脚踝/膝 + 夜间)
    if lab == "yes" and location in ("ankle_heel", "knee") and trigger == "night_rest":
        return ("symptom", "gout_inflammatory", "medium")

    # 规则 4: 血管风险(单侧小腿 + 肿胀样/胀痛)
    if side == "one_side" and location == "calf" and quality in ("distending", "ache"):
        return ("symptom", "vascular_risk", "high")

    # 规则 5: 骨质疏松(年龄大 + 绝经/激素历史 + 夜间痛)
    if (past == "yes" or lab == "yes") and trigger == "night_rest":
        return ("symptom", "osteoporosis_risk", "high")

    # 规则 6: 运动后 + 酸痛 → 肌肉劳损
    if trigger == "after_exercise" and quality in ("ache", "distending"):
        return ("symptom", "muscle_strain", "low")

    # 兜底
    return ("symptom", "muscle_strain", "low")


def classify_answers(
    questionnaire_id: str, answers: dict[str, str]
) -> tuple[str, str, str]:
    """根据量表 id 和用户答案,返回 (scene, tag, risk_level)。

    - scene: "report" | "symptom"
    - tag: 方案 tag(对应 solutions 中的 key)
    - risk_level: "low" | "medium" | "high" | "urgent"
    """
    if questionnaire_id == "bone_density_v1":
        return _classify_bone_density(answers)
    if questionnaire_id == "leg_pain_v1":
        return _classify_leg_pain(answers)
    raise ValueError(f"unknown questionnaire_id: {questionnaire_id}")
