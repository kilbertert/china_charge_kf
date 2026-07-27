"""Executable contract checks for the checked-in health Dify workflow."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from health_consult.questionnaire import BONE_DENSITY_QUESTIONNAIRE, LEG_PAIN_QUESTIONNAIRE


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = (
    ROOT
    / "Workflow-China_charge_seriver-draft-9380"
    / "workflow"
    / "AI_health_consultant_v2.yml"
)


def _graph() -> dict:
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return data["workflow"]["graph"]


def _node(node_id: str) -> dict:
    return next(node for node in _graph()["nodes"] if str(node.get("id")) == node_id)


def _main(node_id: str):
    namespace: dict = {}
    exec(compile(_node(node_id)["data"]["code"], f"workflow-node-{node_id}", "exec"), namespace)
    return namespace["main"]


def test_report_answer_branch_requires_has_answers_true() -> None:
    condition = _node("4105")["data"]["cases"][0]["conditions"][0]
    assert condition["variable_selector"] == ["4104", "has_answers"]
    assert condition["value"] is True


def test_symptom_questionnaire_matches_shared_catalog() -> None:
    result = _main("4024")("leg_pain", "leg_pain_v1", "{}")
    payload = json.loads(result["payload_json"])
    assert [item["id"] for item in payload["questions"]] == [
        item["id"] for item in LEG_PAIN_QUESTIONNAIRE["questions"]
    ]


def test_symptom_complete_returns_canonical_solution_ref() -> None:
    answers = {
        "sudden_severe": "no",
        "weakness_numbness": "no",
        "location": "calf",
        "duration": "lt_1d",
        "trigger": "after_exercise",
    }
    result = _main("4024")(
        "leg_pain", "leg_pain_v1", json.dumps(answers, ensure_ascii=False)
    )
    payload = json.loads(result["payload_json"])
    assert payload["tag"] == "muscle_strain"
    assert payload["solutionRef"] == "muscle_strain_v1"


def test_report_questions_match_shared_catalog() -> None:
    llm_output = {
        "confidence": "high",
        "dataComplete": True,
        "metrics": [{"name": "腰椎 L1-L4 T值", "value": -2.1, "unit": ""}],
        "oneLineConclusion": "骨量减少初筛结果。",
        "problemPriority": [],
        "followUpQuestions": [{"id": "random", "text": "随机题", "options": []}],
    }
    result = _main("4011")(json.dumps(llm_output, ensure_ascii=False))
    output = json.loads(result["output"])
    assert [item["id"] for item in output["payload"]["questions"]] == [
        item["id"] for item in BONE_DENSITY_QUESTIONNAIRE["questions"]
    ]


def test_report_done_payload_has_solution_ref_and_discriminator() -> None:
    result = _main("4121")(
        json.dumps(
            {
                "tag": "menopause_related",
                "risk_level": "medium",
                "confidence": 0.9,
                "reasoning": "已绝经",
                "missingEvidence": [],
            },
            ensure_ascii=False,
        )
    )
    output = json.loads(result["output"])
    assert output["payloadKind"] == "report_done"
    assert output["payload"]["solutionRef"] == "menopause_related_v1"
