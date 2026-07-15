"""Smoke-test the working example end-to-end (offline, no SSH).

Builds the workflow from the high-level API, runs the inline code test
against the embedded test cases, and asserts the same 10/10 pass rate
that we saw in production.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))

import health_consult_v2 as ex  # noqa: E402
from dify_workflow_toolkit.verifier import run_code_test  # noqa: E402


def test_workflow_builds():
    wf = ex.build_workflow()
    assert len(wf.nodes()) == 4
    assert len(wf.edges()) == 3
    ids = [n.id for n in wf.nodes()]
    assert ids == ["4001", "4080", "4002", "4099"]


def test_workflow_validates_and_emits_yaml():
    wf = ex.build_workflow()
    yml = wf.to_yaml()
    assert "scene_classifier_LLM" in yml
    assert "scene_classifier_safety_net" in yml
    assert "langgenius/doubao" in yml


def test_all_production_test_cases_pass_offline():
    cases = ex.build_test_cases()
    passed = 0
    for c in cases:
        llm_text = ex.MOCK_LLM.get(c.case_id, "")
        result = run_code_test(
            ex.CODE_SAFETY_NET,
            inputs={"text": c.text, "has_image": c.has_image, "answers": c.answers},
            llm_text=llm_text,
        )
        exp_conf_s = c.expected.get("scene_confidence", ">=0.0")
        threshold = float(exp_conf_s.lstrip(">=").lstrip("<=")) if isinstance(exp_conf_s, str) else exp_conf_s
        exp_scene = c.expected.get("scene", "")
        if result.get("scene") == exp_scene and result.get("scene_confidence", 0) >= threshold:
            passed += 1
    assert passed == len(cases), f"only {passed}/{len(cases)} passed"
