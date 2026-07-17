"""场景识别 + 风险分层 — 本地兜底逻辑。

当 Dify 调用失败时,scene_router 用纯关键词匹配继续提供可用响应。
置信度 confidence 字段用于告诉前端"本地兜底了,用户可考虑重试"。

Scope (MVP):
- 三场景分流:report / symptom / product
- 危险信号识别:仅对 symptom 场景
"""

from __future__ import annotations

import re
from typing import Optional

from .compliance_loader import get_config


SCENE_REPORT = "report"
SCENE_SYMPTOM = "symptom"
SCENE_PRODUCT = "product"
SCENE_CHITCHAT = "chitchat"  # 问候 / 闲聊 / 寒暄 — 不进入问诊流程

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_URGENT = "urgent"


# ── 合规规则 (单一事实源 shared/compliance.yaml) ────────────
_cfg = get_config()

# 关键词集合 (chitchat 优先匹配, 避免"你好"被误判症状)
_CHITCHAT_KEYWORDS = _cfg.keywords("chitchat")
_REPORT_KEYWORDS = _cfg.keywords("report")
_SYMPTOM_KEYWORDS = _cfg.keywords("symptom")
_PRODUCT_KEYWORDS = _cfg.keywords("product")

# 危险信号词 - 命中任一即判定 urgent
_URGENT_PHRASES = _cfg.urgent_phrases

# T 值数字识别(腰椎 / 股骨 / 全髋) / "XX岁,女/男"
_T_VALUE_RE = re.compile(_cfg.regex_pattern("t_value"), re.IGNORECASE)
_AGE_GENDER_RE = re.compile(_cfg.regex_pattern("age_gender"), re.IGNORECASE)


def classify_scene(text: str) -> tuple[str, float]:
    """根据输入文本判断场景,返回 (scene, confidence)。

    confidence:
      - 1.0  命中关键词,确定
      - 0.6  模糊命中(只有一处弱信号)
      - 0.3  完全无信号,默认 symptom
      - 0.9  命中 chitchat 关键词(问候 / 闲聊)
    """
    if not text or not text.strip():
        return (SCENE_SYMPTOM, 0.3)

    text_lower = text.strip().lower()
    # chitchat 优先匹配 — 避免"你好"被误判为症状
    # 只匹配开头(精确/前缀),避免"现在不能走路"中含"在不"子串的误判
    for kw in _CHITCHAT_KEYWORDS:
        kw_l = kw.lower()
        if text_lower == kw_l or text_lower.startswith(kw_l):
            return (SCENE_CHITCHAT, 0.9)

    # 优先级:report > product > symptom
    # 体检报告场景的关键词最具体,先匹配
    report_hits = sum(1 for kw in _REPORT_KEYWORDS if kw in text)
    if report_hits >= 2:
        return (SCENE_REPORT, 1.0)
    if report_hits == 1 or _T_VALUE_RE.search(text) or _AGE_GENDER_RE.search(text):
        # 单关键词 + T 值或岁数 → 仍判定为报告
        return (SCENE_REPORT, 0.7)

    product_hits = sum(1 for kw in _PRODUCT_KEYWORDS if kw in text)
    if product_hits >= 1:
        return (SCENE_PRODUCT, 1.0)

    symptom_hits = sum(1 for kw in _SYMPTOM_KEYWORDS if kw in text)
    if symptom_hits >= 1:
        return (SCENE_SYMPTOM, 1.0)

    return (SCENE_SYMPTOM, 0.3)


def detect_urgent(text: str) -> bool:
    """判断输入文本是否含危险信号词。命中即返回 True。"""
    if not text:
        return False
    for phrase in _URGENT_PHRASES:
        if phrase in text:
            return True
    return False


def scene_to_risk(scene: str, text: str = "") -> str:
    """根据场景与文本给出默认风险等级。

    危险信号优先于任何场景:命中 detect_urgent 即 urgent,避免"胸痛呼吸困难+
    骨密度T值"被 report 关键词抢匹配后归 medium 而错过紧急提示。
    """
    # 危险信号全局闸门,优先于场景分流
    if detect_urgent(text):
        return RISK_URGENT
    # scene->default risk 从 compliance.yaml risk_mapping 读
    return _cfg.risk_for_scene(scene)


def build_fallback_payload(scene: str, risk_level: str, text: str = "") -> dict:
    """构造本地兜底 SceneResponse 的 payload。"""
    from .questionnaire import (
        LEG_PAIN_QUESTIONNAIRE,
        BONE_DENSITY_QUESTIONNAIRE,
    )

    # 危险信号优先于任何场景:命中即给紧急兜底(避免 report 抢匹配错过 urgent)
    # urgent 方案字段从 compliance.yaml 读 (消除硬编码, 与前端 urgent_v1 一致)
    if risk_level == RISK_URGENT:
        sol = _cfg.get_solution("symptom", "urgent") or {}
        return {
            "symptom": "leg_pain",
            "dangerSignals": [
                {"title": "已检测到危险信号", "content": "您的描述包含可能需要紧急评估的症状。"}
            ],
            "riskLevel": RISK_URGENT,
            "department": sol.get("department", "急诊 / 血管外科 / 骨科"),
            "oneLineConclusion": sol.get("oneLineConclusion", "您的症状可能提示需要尽快就医,请优先评估。"),
            "alert": sol.get("alert") or [
                {"icon": "🚨", "title": "尽快就医", "content": "出现一侧小腿肿胀+胸闷气短,警惕肺栓塞;其他危险信号请到急诊或对应专科。"},
            ],
            "lifestyle": sol.get("lifestyle") or [],
            "nutrition": sol.get("nutrition") or [],
            "solutionRef": "urgent_v1",
        }

    if scene == SCENE_CHITCHAT:
        # 问候 / 闲聊:不进入问诊,给一段友好的引导语
        return {
            "text": "您好!我是您的 AI 健康助手。我可以帮您:① 解读体检报告(尤其骨密度);"
                    "② 判断身体不适风险(尤其腿疼);③ 客观介绍营养健康产品。"
                    "请问您想从哪里开始?可以点击下方快捷按钮,或直接描述您的情况。",
            "intentHint": "upload_report | describe_symptom | product_qa",
        }

    if scene == SCENE_SYMPTOM:
        # 非紧急(已过全局 urgent 闸门):给危险信号筛查初始问题
        danger_questions = [q for q in LEG_PAIN_QUESTIONNAIRE["questions"] if q["tag"] == "urgent"]
        return {
            "symptom": "leg_pain",
            "dangerSignals": [],
            "currentStep": "danger_signal",
            "questionnaireRef": LEG_PAIN_QUESTIONNAIRE["id"],
            "questions": danger_questions,
        }

    if scene == SCENE_REPORT:
        return {
            "reportType": "bone_density",
            "currentStep": "questionnaire",
            "questionnaireRef": BONE_DENSITY_QUESTIONNAIRE["id"],
            "questions": BONE_DENSITY_QUESTIONNAIRE["questions"],
            "oneLineConclusion": "(本地兜底) 请先填写骨量减少原因筛查表,我们会分析主要原因。",
        }

    # product
    return {
        "productRef": "",
        "knowledgeBaseAnswer": "(本地兜底) Dify 服务暂不可用,请稍后重试或联系人工客服。",
    }


def get_default_scene_response(
    text: str = "",
    answers: Optional[dict] = None,
) -> dict:
    """当 Dify 失败时,返回本地构造的 SceneResponse dict(不验证,直接转 SceneResponse)。

    关键分支:
    - 提交答案(answers 非空)→ 跳过 scene 分类,按答案中包含的 question id
      推断场景,直接返回 "done" payload(走方案页)。这样即使 Dify
      工作流的 answers 归类节点失败,本地兜底也能给用户一个合理的"建议页"。
    - 新文本(answers 为空)→ 走 scene 分类,可能进问诊量表。
    """
    has_answers = bool(answers and any(answers.values()))

    if has_answers:
        # 从答案的 question id 反推场景
        scene, _ = classify_scene(text or "")
        # 骨密度量表 question id 命中 → report
        bone_qids = ("menopause", "fragility_fracture", "sun_exposure",
                     "calcium_intake", "strength_training", "low_bmi",
                     "steroid_use", "smoke_alcohol", "chronic_disease",
                     "spine_symptom", "vitd_tested", "family_osteoporosis")
        leg_qids = ("sudden_severe", "trauma", "cannot_stand",
                    "red_swollen_hot", "calf_swelling", "chest_discomfort",
                    "fever_chills", "location", "side", "duration",
                    "trigger", "quality", "past_history", "lab_abnormal",
                    "long_term_meds")
        if any(qid in answers for qid in bone_qids):
            scene = SCENE_REPORT
        elif any(qid in answers for qid in leg_qids):
            scene = SCENE_SYMPTOM

        risk = scene_to_risk(scene, text or "")
        if scene == SCENE_REPORT:
            return {
                "scene": SCENE_REPORT,
                "risk_level": RISK_MEDIUM,
                "confidence": 0.5,
                "payload": {
                    "reportType": "bone_density",
                    "oneLineConclusion": "(本地兜底) 已根据您填写的骨量原因筛查表,生成综合建议。",
                    "problemPriority": [],
                    "metrics": [],
                    "tValueChart": {"normal": -1.0, "yours": 0.0,
                                    "thresholds": {"normal": -1.0, "loss": -2.5}},
                    "riskDistribution": [
                        {"name": "中等风险", "value": 60},
                        {"name": "低风险", "value": 40},
                    ],
                    "questionnaireRef": "bone_density_v1",
                },
                "raw": None,
            }
        # 默认按 symptom done 兜底,避免前端卡在量表页
        return {
            "scene": SCENE_SYMPTOM,
            "risk_level": RISK_LOW,
            "confidence": 0.5,
            "payload": {
                "riskLevel": RISK_LOW,
                "possibleDirection": "(本地兜底) 已根据您的描述生成基础建议",
                "department": "骨科 / 全科",
                "redFlag": [],
                "lifestyle": [
                    {"icon": "🚶", "title": "运动调整", "content": "避免长时间负重、爬山、深蹲;选择游泳、骑车等低冲击运动"},
                    {"icon": "⚖️", "title": "控制体重", "content": "维持合理体重,减轻下肢关节负担"},
                ],
                "nutrition": [
                    {"icon": "🥛", "title": "钙", "content": "每日 800-1000mg(饮食 + 补充剂)"},
                    {"icon": "☀️", "title": "维生素D", "content": "每日 400-800IU,配合日晒"},
                    {"icon": "🥩", "title": "优质蛋白", "content": "每日 1.0-1.2g/kg,支持骨骼肌肉"},
                ],
                "alert": [
                    {"icon": "🚨", "title": "尽快就医", "content": "如出现明显红肿热痛 / 夜间痛加重 / 不能站立走路,请尽快到骨科或急诊"},
                ],
                "solutionRef": "symptom_general_v1",
            },
            "raw": None,
        }

    scene, confidence = classify_scene(text)
    risk = scene_to_risk(scene, text)
    payload = build_fallback_payload(scene, risk, text)
    return {
        "scene": scene,
        "risk_level": risk,
        "confidence": confidence,
        "payload": payload,
        "raw": None,
    }
