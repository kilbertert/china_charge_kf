"""FastAPI endpoint smoke test — /health, /version, 404 路径。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from health_consult.main import app

client = TestClient(app)


def test_health_returns_200_and_status():
    r = client.get("/api/health-consult/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "health-consult"
    assert data["version"]


def test_version_returns_200_and_workflow_id():
    r = client.get("/api/health-consult/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "dify_workflow_id" in data
    assert data["dify_workflow_id"]


def test_questionnaire_existing_returns_200():
    r = client.get("/api/health-consult/questionnaire/bone_density_v1")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "bone_density_v1"
    assert data["scene"] == "report"
    assert len(data["questions"]) == 12


def test_questionnaire_leg_pain_returns_200():
    r = client.get("/api/health-consult/questionnaire/leg_pain_v1")
    assert r.status_code == 200
    assert r.json()["scene"] == "symptom"


def test_questionnaire_missing_returns_404():
    r = client.get("/api/health-consult/questionnaire/nonexistent")
    assert r.status_code == 404


def test_solution_existing_returns_200():
    r = client.get("/api/health-consult/solution/report/menopause_related")
    assert r.status_code == 200
    data = r.json()
    assert data["tag"] == "menopause_related"
    assert data["riskLevel"] == "medium"


def test_solution_missing_returns_404():
    r = client.get("/api/health-consult/solution/report/nonexistent")
    assert r.status_code == 404


def test_solution_unknown_scene_returns_404():
    r = client.get("/api/health-consult/solution/product/anything")
    assert r.status_code == 404


def test_chat_endpoint_accepts_form():
    # text-only form; Dify API key empty → 本地兜底应能正常返回
    r = client.post(
        "/api/health-consult/chat",
        data={"text": "我腿疼", "session_id": "test-1", "language": "中文"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["scene"] == "symptom"
    assert "payload" in data
    assert "risk_level" in data


def test_chat_endpoint_with_invalid_answers_json_returns_400():
    r = client.post(
        "/api/health-consult/chat",
        data={"text": "hi", "answers": "not json"},
    )
    assert r.status_code == 400


def test_chat_endpoint_empty_inputs_falls_back():
    r = client.post(
        "/api/health-consult/chat",
        data={"text": ""},
    )
    assert r.status_code == 200
    data = r.json()
    # 空文本 → 默认 symptom 兜底
    assert data["scene"] == "symptom"
