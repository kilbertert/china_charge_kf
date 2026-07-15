"""契约一致性测试。

验证:
- Python 量表/方案数据与 docx 一致(题目数、tag、id、scene、风险等级)
- classify_answers 覆盖 6+6 种归类路径
- get_questionnaire / get_solution / list_* 基本查询正常
"""

from __future__ import annotations

import pytest

from health_consult.questionnaire import (
    ALL_QUESTIONNAIRES,
    BONE_DENSITY_QUESTIONNAIRE,
    LEG_PAIN_QUESTIONNAIRE,
    classify_answers,
    get_questionnaire,
    list_questionnaires,
)
from health_consult.solutions import (
    BONE_DENSITY_SOLUTIONS,
    LEG_PAIN_SOLUTIONS,
    get_solution,
    list_solutions,
)


# ─── 量表基础断言 ─────────────────────────────────────────────

def test_bone_density_question_count():
    assert len(BONE_DENSITY_QUESTIONNAIRE["questions"]) == 12


def test_leg_pain_question_count():
    # A 表 7 + B 表 5(location+side+duration+trigger+quality) + C 表 3 = 15
    assert len(LEG_PAIN_QUESTIONNAIRE["questions"]) == 15


def test_bone_density_6_unique_tags():
    tags = {q["tag"] for q in BONE_DENSITY_QUESTIONNAIRE["questions"]}
    expected = {
        "menopause_related",
        "fracture_high_risk",
        "vitamin_d_deficient",
        "calcium_protein_deficient",
        "exercise_deficient",
        "medication_related",
    }
    assert tags == expected


def test_leg_pain_urgent_signals_present():
    urgent = [q for q in LEG_PAIN_QUESTIONNAIRE["questions"] if q["tag"] == "urgent"]
    assert len(urgent) == 7


def test_leg_pain_b_and_c_sections_present():
    location_qs = [q for q in LEG_PAIN_QUESTIONNAIRE["questions"] if q["tag"] == "location"]
    history_qs = [q for q in LEG_PAIN_QUESTIONNAIRE["questions"] if q["tag"] == "history"]
    assert len(location_qs) == 1  # B 表主问题(其它 B 表题目用 tag=trigger/quality/duration/side)
    assert len(history_qs) == 3    # C 表 3 题


def test_question_unique_ids():
    for q in ALL_QUESTIONNAIRES:
        ids = [qq["id"] for qq in q["questions"]]
        assert len(ids) == len(set(ids)), f"duplicate ids in {q['id']}"


def test_question_options_have_required_keys():
    for q in ALL_QUESTIONNAIRES:
        for qq in q["questions"]:
            assert {"id", "text", "type", "options", "tag"} <= set(qq.keys())
            for opt in qq["options"]:
                assert {"key", "label", "weight"} <= set(opt.keys())


# ─── 方案基础断言 ─────────────────────────────────────────────

def test_bone_density_solution_count():
    assert len(BONE_DENSITY_SOLUTIONS) == 6


def test_leg_pain_solution_count():
    assert len(LEG_PAIN_SOLUTIONS) == 6


def test_bone_density_tags_match_questionnaire():
    sol_tags = set(BONE_DENSITY_SOLUTIONS.keys())
    q_tags = {q["tag"] for q in BONE_DENSITY_QUESTIONNAIRE["questions"]}
    assert sol_tags == q_tags


def test_leg_pain_tags_match_classify_outputs():
    # 6 种方案 tag 必须在 classify_answers 返回值中可达
    sol_tags = set(LEG_PAIN_SOLUTIONS.keys())
    assert "vascular_risk" in sol_tags  # urgent 路径
    assert "muscle_strain" in sol_tags  # 兜底


def test_solution_required_fields():
    for sol in list(BONE_DENSITY_SOLUTIONS.values()) + list(LEG_PAIN_SOLUTIONS.values()):
        assert {"id", "scene", "tag", "title", "riskLevel", "department",
                "oneLineConclusion", "lifestyle", "nutrition", "alert"} <= set(sol.keys())
        assert sol["lifestyle"], f"empty lifestyle in {sol['id']}"
        assert sol["nutrition"], f"empty nutrition in {sol['id']}"
        assert sol["alert"], f"empty alert in {sol['id']}"
        for section in sol["lifestyle"] + sol["nutrition"] + sol["alert"]:
            assert {"icon", "title", "content"} <= set(section.keys())


# ─── 查询函数 ─────────────────────────────────────────────────

def test_get_questionnaire_existing():
    q = get_questionnaire("bone_density_v1")
    assert q is not None
    assert q["id"] == "bone_density_v1"


def test_get_questionnaire_missing_returns_none():
    assert get_questionnaire("nonexistent") is None


def test_list_questionnaires_returns_both():
    qs = list_questionnaires()
    assert len(qs) == 2
    assert {q["id"] for q in qs} == {"bone_density_v1", "leg_pain_v1"}


def test_get_solution_report():
    s = get_solution("report", "menopause_related")
    assert s is not None
    assert s["tag"] == "menopause_related"


def test_get_solution_symptom():
    s = get_solution("symptom", "knee_degeneration")
    assert s is not None


def test_get_solution_missing_returns_none():
    assert get_solution("report", "nonexistent") is None
    assert get_solution("product", "x") is None


def test_list_solutions_returns_correct_count():
    assert len(list_solutions("report")) == 6
    assert len(list_solutions("symptom")) == 6
    assert list_solutions("product") == []


# ─── classify_answers 覆盖测试 ───────────────────────────────

def test_classify_bone_density_menopause_yes():
    scene, tag, risk = classify_answers("bone_density_v1", {"menopause": "yes"})
    assert scene == "report"
    assert tag == "menopause_related"


def test_classify_bone_density_vitamin_d():
    scene, tag, risk = classify_answers("bone_density_v1", {
        "sun_exposure": "yes",
        "vitd_tested": "low",
    })
    assert tag == "vitamin_d_deficient"


def test_classify_bone_density_fracture_high_risk():
    scene, tag, risk = classify_answers("bone_density_v1", {
        "fragility_fracture": "yes",
        "spine_symptom": "yes",
    })
    assert tag == "fracture_high_risk"
    assert risk == "high"


def test_classify_bone_density_calcium_protein():
    scene, tag, risk = classify_answers("bone_density_v1", {
        "calcium_intake": "yes",
        "low_bmi": "yes",
    })
    assert tag == "calcium_protein_deficient"


def test_classify_bone_density_exercise():
    scene, tag, risk = classify_answers("bone_density_v1", {
        "strength_training": "yes",
    })
    assert tag == "exercise_deficient"


def test_classify_bone_density_medication():
    scene, tag, risk = classify_answers("bone_density_v1", {
        "steroid_use": "yes",
        "chronic_disease": "yes",
    })
    assert tag == "medication_related"
    assert risk == "high"


def test_classify_leg_pain_urgent_trauma():
    scene, tag, risk = classify_answers("leg_pain_v1", {"trauma": "yes"})
    assert scene == "symptom"
    assert tag == "vascular_risk"
    assert risk == "urgent"


def test_classify_leg_pain_urgent_chest():
    scene, tag, risk = classify_answers("leg_pain_v1", {"chest_discomfort": "yes"})
    assert risk == "urgent"


def test_classify_leg_pain_urgent_calf_swelling():
    scene, tag, risk = classify_answers("leg_pain_v1", {"calf_swelling": "yes"})
    assert risk == "urgent"


def test_classify_leg_pain_knee():
    scene, tag, risk = classify_answers("leg_pain_v1", {
        "location": "knee",
        "trigger": "stairs",
    })
    assert tag == "knee_degeneration"


def test_classify_leg_pain_muscle_strain():
    scene, tag, risk = classify_answers("leg_pain_v1", {
        "trigger": "after_exercise",
        "quality": "ache",
    })
    assert tag == "muscle_strain"


def test_classify_leg_pain_lumbar():
    scene, tag, risk = classify_answers("leg_pain_v1", {
        "quality": "numb",
        "location": "radiating",
    })
    assert tag == "lumbar_radiculopathy"


def test_classify_leg_pain_gout():
    scene, tag, risk = classify_answers("leg_pain_v1", {
        "lab_abnormal": "yes",
        "location": "ankle_heel",
        "trigger": "night_rest",
    })
    assert tag == "gout_inflammatory"


def test_classify_leg_pain_vascular_high_risk():
    scene, tag, risk = classify_answers("leg_pain_v1", {
        "side": "one_side",
        "location": "calf",
        "quality": "distending",
    })
    assert tag == "vascular_risk"
    assert risk == "high"


def test_classify_leg_pain_osteoporosis_risk():
    scene, tag, risk = classify_answers("leg_pain_v1", {
        "past_history": "yes",
        "trigger": "night_rest",
    })
    assert tag == "osteoporosis_risk"


def test_classify_leg_pain_empty_answers_fallback():
    scene, tag, risk = classify_answers("leg_pain_v1", {})
    assert scene == "symptom"
    assert risk in ("low", "medium", "high", "urgent")


def test_classify_unknown_questionnaire_raises():
    with pytest.raises(ValueError):
        classify_answers("nonexistent", {})
