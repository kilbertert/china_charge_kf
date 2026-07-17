"""solutions 查询测试 — 12 个 tag 全部可查 + 错误 tag 返回 None。"""

from __future__ import annotations

from health_consult.solutions import (
    BONE_DENSITY_SOLUTIONS,
    LEG_PAIN_SOLUTIONS,
    get_solution,
    list_solutions,
)


# ─── 6 个骨密度 tag ────────────────────────────────────────────
def test_bone_density_menopause_related():
    s = get_solution("report", "menopause_related")
    assert s is not None
    assert s["riskLevel"] == "medium"


def test_bone_density_vitamin_d_deficient():
    s = get_solution("report", "vitamin_d_deficient")
    assert s is not None


def test_bone_density_calcium_protein_deficient():
    s = get_solution("report", "calcium_protein_deficient")
    assert s is not None
    assert s["riskLevel"] == "low"


def test_bone_density_exercise_deficient():
    s = get_solution("report", "exercise_deficient")
    assert s is not None


def test_bone_density_medication_related():
    s = get_solution("report", "medication_related")
    assert s is not None
    assert s["riskLevel"] == "high"


def test_bone_density_fracture_high_risk():
    s = get_solution("report", "fracture_high_risk")
    assert s is not None
    assert s["riskLevel"] == "high"


# ─── 6 个腿疼 tag ──────────────────────────────────────────────
def test_leg_pain_muscle_strain():
    s = get_solution("symptom", "muscle_strain")
    assert s is not None
    assert s["riskLevel"] == "low"


def test_leg_pain_knee_degeneration():
    s = get_solution("symptom", "knee_degeneration")
    assert s is not None
    assert s["riskLevel"] == "medium"


def test_leg_pain_lumbar_radiculopathy():
    s = get_solution("symptom", "lumbar_radiculopathy")
    assert s is not None


def test_leg_pain_gout_inflammatory():
    s = get_solution("symptom", "gout_inflammatory")
    assert s is not None


def test_leg_pain_vascular_risk():
    s = get_solution("symptom", "vascular_risk")
    assert s is not None
    assert s["riskLevel"] == "high"


def test_leg_pain_osteoporosis_risk():
    s = get_solution("symptom", "osteoporosis_risk")
    assert s is not None
    assert s["riskLevel"] == "high"


# ─── 错误 tag / scene 边界 ────────────────────────────────────
def test_missing_tag_in_report_returns_none():
    assert get_solution("report", "nonexistent") is None


def test_missing_tag_in_symptom_returns_none():
    assert get_solution("symptom", "nonexistent") is None


def test_unknown_scene_returns_none():
    assert get_solution("product", "anything") is None
    assert get_solution("unknown", "anything") is None


def test_product_scene_returns_none_for_bone_tags():
    # product scene 不支持骨密度 tag
    assert get_solution("product", "menopause_related") is None


def test_report_scene_returns_none_for_leg_tags():
    assert get_solution("report", "muscle_strain") is None


# ─── list_solutions 数量正确 ──────────────────────────────────
def test_list_bone_density_solutions_count():
    assert len(list_solutions("report")) == 6


def test_list_leg_pain_solutions_count():
    # 6 个方向方案 + urgent_v1 = 7 (urgent_v1 已合规: 空 lifestyle/nutrition)
    assert len(list_solutions("symptom")) == 7


def test_list_product_solutions_empty():
    assert list_solutions("product") == []


# ─── 字典数量兜底 ─────────────────────────────────────────────
def test_total_solutions_count():
    assert len(BONE_DENSITY_SOLUTIONS) == 6
    assert len(LEG_PAIN_SOLUTIONS) == 7


# ─── 字段完整性 ───────────────────────────────────────────────
def test_all_solutions_have_required_sections():
    # report 方案: 边界允许给营养/处置建议 -> lifestyle/nutrition 非空
    for sol in list(BONE_DENSITY_SOLUTIONS.values()):
        assert sol["lifestyle"], f"empty lifestyle: {sol['id']}"
        assert sol["nutrition"], f"empty nutrition: {sol['id']}"
        assert sol["alert"], f"empty alert: {sol['id']}"
        assert sol["department"]
        assert sol["oneLineConclusion"]
    # symptom 方案: 边界禁止处置意见/营养处方 -> lifestyle/nutrition 必须为空
    # (仅保留方向/科室/就医提醒 alert)
    for sol in list(LEG_PAIN_SOLUTIONS.values()):
        assert sol["lifestyle"] == [], f"symptom {sol['id']} must have empty lifestyle (compliance)"
        assert sol["nutrition"] == [], f"symptom {sol['id']} must have empty nutrition (compliance)"
        assert sol["alert"], f"empty alert: {sol['id']}"
        assert sol["department"]
        assert sol["oneLineConclusion"]
