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


# ─── 骨密度 12 题 ──────────────────────────────────────────────
BONE_DENSITY_QUESTIONNAIRE: Questionnaire = {
    "id": "bone_density_v1",
    "scene": "report",
    "title": "骨量减少原因筛查表",
    "description": "为了判断您为什么骨量下降,请填写以下问题",
    "questions": [
        {
            "id": "menopause",
            "text": "是否已经绝经?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "menopause_related",
        },
        {
            "id": "fragility_fracture",
            "text": "是否有轻微摔倒后骨折史?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "fracture_high_risk",
        },
        {
            "id": "family_osteoporosis",
            "text": "父母是否有髋部骨折或骨质疏松?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 2},
            ],
            "tag": "fracture_high_risk",
        },
        {
            "id": "sun_exposure",
            "text": "平时晒太阳是否较少?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 2},
            ],
            "tag": "vitamin_d_deficient",
        },
        {
            "id": "calcium_intake",
            "text": "是否很少喝奶、吃豆制品或高钙食物?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 2},
            ],
            "tag": "calcium_protein_deficient",
        },
        {
            "id": "strength_training",
            "text": "是否缺乏力量训练或负重运动?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 2},
            ],
            "tag": "exercise_deficient",
        },
        {
            "id": "low_bmi",
            "text": "是否体重偏低或近期明显减重?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 1},
            ],
            "tag": "calcium_protein_deficient",
        },
        {
            "id": "steroid_use",
            "text": "是否长期服用激素类药物?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "medication_related",
        },
        {
            "id": "smoke_alcohol",
            "text": "是否经常饮酒或吸烟?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 1},
            ],
            "tag": "medication_related",
        },
        {
            "id": "chronic_disease",
            "text": "是否有甲状腺、肾病、肝病等问题?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 2},
            ],
            "tag": "medication_related",
        },
        {
            "id": "spine_symptom",
            "text": "是否有腰背痛、身高变矮、驼背加重?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "fracture_high_risk",
        },
        {
            "id": "vitd_tested",
            "text": "是否检查过 25-OH 维生素 D?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "low", "label": "是,结果偏低", "weight": 2},
                {"key": "normal", "label": "是,结果正常", "weight": 0},
            ],
            "tag": "vitamin_d_deficient",
        },
    ],
}


# ─── 腿疼 A+B+C 三表 ──────────────────────────────────────────
LEG_PAIN_QUESTIONNAIRE: Questionnaire = {
    "id": "leg_pain_v1",
    "scene": "symptom",
    "title": "腿疼症状甄别表",
    "description": "先判断危险信号,再定位疼痛特点,最后补充病史",
    "questions": [
        # A 表:危险信号 7 题
        {
            "id": "sudden_severe",
            "text": "腿疼是不是突然发生、并且疼痛很剧烈?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "urgent",
        },
        {
            "id": "trauma",
            "text": "最近有没有摔倒、扭伤、撞伤,之后出现腿疼?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "urgent",
        },
        {
            "id": "cannot_stand",
            "text": "现在是否不能站立、不能走路或无法负重?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "urgent",
        },
        {
            "id": "red_swollen_hot",
            "text": "腿部有没有明显红、肿、热、痛?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 2},
            ],
            "tag": "urgent",
        },
        {
            "id": "calf_swelling",
            "text": "是否一侧小腿明显肿胀、发紧、发热,按压疼痛?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "urgent",
        },
        {
            "id": "chest_discomfort",
            "text": "是否伴有胸闷、胸痛、呼吸困难?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 3},
            ],
            "tag": "urgent",
        },
        {
            "id": "fever_chills",
            "text": "是否有发热、寒战,或局部皮肤破溃感染?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 2},
            ],
            "tag": "urgent",
        },
        # B 表:定位量表 4 题
        {
            "id": "location",
            "text": "您主要疼在哪里?",
            "type": "single",
            "options": [
                {"key": "hip", "label": "髋部/大腿根", "weight": 0},
                {"key": "thigh_front", "label": "大腿前侧", "weight": 0},
                {"key": "thigh_back", "label": "大腿后侧", "weight": 0},
                {"key": "knee", "label": "膝盖", "weight": 0},
                {"key": "calf", "label": "小腿", "weight": 0},
                {"key": "ankle_heel", "label": "脚踝/足跟", "weight": 0},
                {"key": "radiating", "label": "整条腿放射样疼痛", "weight": 0},
            ],
            "tag": "location",
        },
        {
            "id": "side",
            "text": "是一侧疼还是两侧疼?",
            "type": "single",
            "options": [
                {"key": "one_side", "label": "一侧", "weight": 0},
                {"key": "both", "label": "两侧", "weight": 0},
                {"key": "unsure", "label": "不确定", "weight": 0},
            ],
            "tag": "side",
        },
        {
            "id": "duration",
            "text": "疼痛持续多久了?",
            "type": "single",
            "options": [
                {"key": "lt_1d", "label": "1天以内", "weight": 0},
                {"key": "d_2_7", "label": "2-7天", "weight": 0},
                {"key": "w_1_4", "label": "1-4周", "weight": 0},
                {"key": "gt_1m", "label": "超过1个月", "weight": 0},
                {"key": "recurrent", "label": "反复发作", "weight": 0},
            ],
            "tag": "duration",
        },
        {
            "id": "trigger",
            "text": "疼痛是怎么出现的?什么情况下更痛?",
            "type": "single",
            "options": [
                {"key": "after_exercise", "label": "运动后出现", "weight": 0},
                {"key": "after_sit_stand", "label": "久坐久站后出现", "weight": 0},
                {"key": "stairs", "label": "走路上下楼明显", "weight": 0},
                {"key": "night_rest", "label": "夜间或休息时明显", "weight": 0},
                {"key": "no_cause", "label": "没有明显诱因", "weight": 0},
            ],
            "tag": "trigger",
        },
        {
            "id": "quality",
            "text": "疼痛性质更像哪一种?",
            "type": "single",
            "options": [
                {"key": "ache", "label": "酸痛", "weight": 0},
                {"key": "distending", "label": "胀痛", "weight": 0},
                {"key": "stabbing", "label": "刺痛", "weight": 0},
                {"key": "burning", "label": "灼痛", "weight": 0},
                {"key": "numb", "label": "麻痛", "weight": 0},
                {"key": "cramp", "label": "抽筋样疼", "weight": 0},
                {"key": "deep_joint", "label": "关节深处痛", "weight": 0},
            ],
            "tag": "quality",
        },
        # C 表:伴随症状与病史 3 题
        {
            "id": "past_history",
            "text": "是否有腰椎间盘突出、骨质疏松、痛风、糖尿病等病史?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 0},
                {"key": "unsure", "label": "不清楚", "weight": 0},
            ],
            "tag": "history",
        },
        {
            "id": "lab_abnormal",
            "text": "最近体检是否提示尿酸高、骨密度低、血糖高或炎症指标异常?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 0},
                {"key": "unsure", "label": "不清楚", "weight": 0},
            ],
            "tag": "history",
        },
        {
            "id": "long_term_meds",
            "text": "是否长期服用激素、抗凝药或其他慢病药物?",
            "type": "single",
            "options": [
                {"key": "no", "label": "否", "weight": 0},
                {"key": "yes", "label": "是", "weight": 0},
                {"key": "unsure", "label": "不清楚", "weight": 0},
            ],
            "tag": "history",
        },
    ],
}

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
_BONE_DENSITY_RISK = {
    "menopause_related": "medium",
    "vitamin_d_deficient": "medium",
    "calcium_protein_deficient": "low",
    "exercise_deficient": "low",
    "medication_related": "high",
    "fracture_high_risk": "high",
}

# 腿疼 6 种类型 → 风险等级
_LEG_PAIN_RISK = {
    "muscle_strain": "low",
    "knee_degeneration": "medium",
    "lumbar_radiculopathy": "medium",
    "gout_inflammatory": "medium",
    "vascular_risk": "high",
    "osteoporosis_risk": "high",
}


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
    if scores.get("fracture_high_risk", 0) >= 3:
        return ("report", "fracture_high_risk", "high")
    tag = max(scores, key=lambda k: scores[k])
    risk = _BONE_DENSITY_RISK.get(tag, "low")
    return ("report", tag, risk)


def _classify_leg_pain(answers: dict[str, str]) -> tuple[str, str, str]:
    """腿疼答案归类:
    - A 表(危险信号)任一命中 weight>=3 → urgent(直接血管/急诊路径)
    - 否则按 B+C 表答案匹配 6 种类型
    """
    urgent_questions = [q for q in LEG_PAIN_QUESTIONNAIRE["questions"] if q["tag"] == "urgent"]
    for q in urgent_questions:
        ans = answers.get(q["id"])
        if ans is None:
            continue
        for opt in q["options"]:
            if opt["key"] == ans and opt["weight"] >= 2:
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
