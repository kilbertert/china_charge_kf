"""scene_router 本地兜底逻辑测试。

覆盖:
- 三场景(report/symptom/product)关键词识别,每个场景 ≥3 用例
- 危险信号识别
- fallback payload 构造
"""

from __future__ import annotations

from health_consult.scene_router import (
    SCENE_PRODUCT,
    SCENE_REPORT,
    SCENE_SYMPTOM,
    build_fallback_payload,
    classify_scene,
    detect_urgent,
    get_default_scene_response,
    scene_to_risk,
)


# ── report 场景 ────────────────────────────────────────────────
def test_report_bone_density_phrase():
    scene, conf = classify_scene("56岁女性,腰椎 T值 -2.1,骨量减少")
    assert scene == SCENE_REPORT
    assert conf >= 0.7


def test_report_dxa_keyword():
    scene, conf = classify_scene("请看 DXA 报告,骨密度 T 值 -1.8")
    assert scene == SCENE_REPORT
    assert conf >= 1.0


def test_report_age_gender_pattern():
    scene, conf = classify_scene("62岁,女,体检发现骨密度偏低")
    assert scene == SCENE_REPORT


def test_report_osteoporosis_term():
    scene, _ = classify_scene("骨质疏松,腰椎 T 值 -2.8")
    assert scene == SCENE_REPORT


# ── symptom 场景 ───────────────────────────────────────────────
def test_symptom_simple_pain():
    scene, conf = classify_scene("我腿疼")
    assert scene == SCENE_SYMPTOM
    assert conf >= 1.0


def test_symptom_swelling():
    scene, _ = classify_scene("膝盖肿胀难受")
    assert scene == SCENE_SYMPTOM


def test_symptom_chest_discomfort():
    scene, _ = classify_scene("胸闷气短呼吸困难")
    assert scene == SCENE_SYMPTOM


def test_symptom_cant_walk():
    scene, _ = classify_scene("现在不能走路了,麻木无力")
    assert scene == SCENE_SYMPTOM


# ── product 场景 ───────────────────────────────────────────────
def test_product_can_i_eat():
    # 注意不要含 report 关键词(骨密度/骨质疏松/DXA 等),否则会先命中 report
    scene, conf = classify_scene("请问老人能不能吃氨糖软骨素?")
    assert scene == SCENE_PRODUCT
    assert conf >= 1.0


def test_product_supplement_recommendation():
    scene, _ = classify_scene("保健食品哪个更适合?推荐一下补钙的")
    assert scene == SCENE_PRODUCT


def test_product_vitamin_d_supplement():
    scene, _ = classify_scene("维生素D 营养品适不适合老年人吃")
    assert scene == SCENE_PRODUCT


# ── 空 / 默认 ──────────────────────────────────────────────────
def test_empty_text_defaults_symptom():
    scene, conf = classify_scene("")
    assert scene == SCENE_SYMPTOM
    assert conf == 0.3


def test_irrelevant_text_defaults_symptom():
    scene, conf = classify_scene("今天天气真好")
    assert scene == SCENE_SYMPTOM
    assert conf == 0.3


# ── 危险信号 ───────────────────────────────────────────────────
def test_urgent_chest_pain():
    assert detect_urgent("突然胸痛,呼吸困难") is True


def test_urgent_calf_swelling():
    assert detect_urgent("一侧小腿肿胀发热,按压疼痛") is True


def test_urgent_cant_walk():
    assert detect_urgent("不能走路,腿无力") is True


def test_urgent_numbness():
    assert detect_urgent("腿部麻木无力,无法站立") is True


def test_no_urgent_normal_pain():
    assert detect_urgent("运动后肌肉酸痛") is False


def test_no_urgent_empty():
    assert detect_urgent("") is False


# ── risk level ─────────────────────────────────────────────────
def test_symptom_with_urgent_risk():
    risk = scene_to_risk(SCENE_SYMPTOM, "胸痛呼吸困难")
    assert risk == "urgent"


def test_symptom_without_urgent_low():
    risk = scene_to_risk(SCENE_SYMPTOM, "运动后酸痛")
    assert risk == "low"


def test_report_default_medium():
    assert scene_to_risk(SCENE_REPORT, "") == "medium"


def test_product_default_low():
    assert scene_to_risk(SCENE_PRODUCT, "") == "low"


# ── fallback payload ───────────────────────────────────────────
def test_fallback_symptom_returns_questions():
    p = build_fallback_payload(SCENE_SYMPTOM, "low")
    assert p["currentStep"] == "danger_signal"
    assert p["questionnaireRef"] == "leg_pain_v1"
    assert len(p["questions"]) == 7  # A 表 7 题


def test_fallback_symptom_urgent_returns_alert():
    p = build_fallback_payload(SCENE_SYMPTOM, "urgent", "胸痛呼吸困难")
    assert p["riskLevel"] == "urgent"
    assert len(p["alert"]) >= 1


def test_fallback_report_returns_questionnaire_ref():
    p = build_fallback_payload(SCENE_REPORT, "medium")
    assert p["reportType"] == "bone_density"
    assert p["questionnaireRef"] == "bone_density_v1"


def test_fallback_product_default_message():
    p = build_fallback_payload(SCENE_PRODUCT, "low")
    assert "knowledgeBaseAnswer" in p


def test_get_default_scene_response_shape():
    r = get_default_scene_response(text="我腿疼")
    assert r["scene"] == SCENE_SYMPTOM
    assert "payload" in r
    assert "confidence" in r
