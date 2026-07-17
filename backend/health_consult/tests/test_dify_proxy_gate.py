"""回归测试 - P1-1 后端确定性 urgent 闸门 + P1-2 PDF 文件类型映射。

覆盖 review 指出的关键逻辑:
- mixed urgent: Dify 对"胸痛呼吸困难,骨密度T值-2.8"返 report/medium 时, 后端闸门覆盖为 urgent
- 非 urgent 文本不被误覆盖 (闸门不误伤)
- _dify_file_type: PDF->document / image / audio / 未知兜底 document
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from health_consult.config import settings
from health_consult import dify_proxy
from health_consult.dify_proxy import _dify_file_type, chat_with_dify


def _setup_fake_dify(monkeypatch, output_dict: dict) -> MagicMock:
    """配置 dify_proxy 使用 mock DifyClient, 返回 output_dict 解析后的 workflow 输出。"""
    monkeypatch.setattr(settings, "dify_api_key", "fake-key-test")
    dify_proxy._client = None  # 重置单例, 避免其他用例污染
    fake_body = {
        "data": {"outputs": {settings.dify_output_text: json.dumps(output_dict, ensure_ascii=False)}}
    }
    mock_client = MagicMock()
    mock_client.run_workflow = AsyncMock(return_value=fake_body)
    return mock_client


def test_urgent_gate_overrides_dify_report_medium(monkeypatch):
    """review 反例: Dify 把'胸痛呼吸困难+T值-2.8'判 report/medium,
    后端 urgent 闸门必须覆盖为 urgent (场景分流漏 urgent 的兜底)。"""
    mock_client = _setup_fake_dify(
        monkeypatch,
        {
            "scene": "report",
            "risk_level": "medium",
            "confidence": 0.9,
            "payload": {"reportType": "bone_density", "oneLineConclusion": "骨密度下降"},
        },
    )
    with patch("health_consult.dify_proxy.get_dify_client", return_value=mock_client):
        result = asyncio.run(
            chat_with_dify(text="胸痛呼吸困难,骨密度T值-2.8", language="中文")
        )
    assert result["risk_level"] == "urgent"
    assert result["scene"] == "symptom"
    assert result["payload"]["riskLevel"] == "urgent"
    assert result["payload"]["solutionRef"] == "urgent_v1"


def test_urgent_gate_preserves_dify_urgent(monkeypatch):
    """Dify 已判 urgent 时, 闸门不重复覆盖 (保持 Dify 的 urgent payload)。"""
    mock_client = _setup_fake_dify(
        monkeypatch,
        {
            "scene": "symptom",
            "risk_level": "urgent",
            "confidence": 0.8,
            "payload": {"riskLevel": "urgent", "solutionRef": "urgent_v1", "department": "急诊"},
        },
    )
    with patch("health_consult.dify_proxy.get_dify_client", return_value=mock_client):
        result = asyncio.run(
            chat_with_dify(text="胸痛呼吸困难,骨密度T值-2.8", language="中文")
        )
    assert result["risk_level"] == "urgent"


def test_urgent_gate_does_not_fire_on_non_urgent(monkeypatch):
    """非 urgent 文本 (无危险信号词) 不被闸门误覆盖, 保留 Dify 判断。"""
    mock_client = _setup_fake_dify(
        monkeypatch,
        {
            "scene": "report",
            "risk_level": "medium",
            "confidence": 0.9,
            "payload": {"reportType": "bone_density", "oneLineConclusion": "骨量减少"},
        },
    )
    with patch("health_consult.dify_proxy.get_dify_client", return_value=mock_client):
        result = asyncio.run(
            chat_with_dify(text="我的骨密度T值是-1.5,想咨询一下", language="中文")
        )
    assert result["risk_level"] == "medium"
    assert result["scene"] == "report"


# ── P1-2 PDF 文件类型映射 ──────────────────────────────────────
def test_dify_file_type_pdf_is_document():
    assert _dify_file_type("application/pdf", "report.pdf") == "document"


def test_dify_file_type_pdf_by_extension():
    assert _dify_file_type("", "scan.PDF") == "document"


def test_dify_file_type_image():
    assert _dify_file_type("image/png", "x.png") == "image"
    assert _dify_file_type("image/jpeg", "x.jpg") == "image"


def test_dify_file_type_audio_video():
    assert _dify_file_type("audio/webm", "rec.webm") == "audio"
    assert _dify_file_type("video/mp4", "clip.mp4") == "video"


def test_dify_file_type_unknown_defaults_document():
    assert _dify_file_type("application/octet-stream", "x.bin") == "document"
    assert _dify_file_type("", "") == "document"


def test_dify_file_type_office_is_document():
    assert _dify_file_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "doc.docx") == "document"


# ── P1-a 复审: 问卷答案路径 urgent 闸门 ──────────────────────
# 症状问卷提交时不发文本(HealthConsultApp.handleSubmitAnswers), 工作流 URGENT_ANSWER_KEYS
# 又缺 red_swollen_hot/calf_swelling/fever_chills -> Dify 返 symptom/medium。后端须对 answers 兜底。
def test_urgent_gate_answers_red_swollen_hot(monkeypatch):
    """空文本 + red_swollen_hot=yes + Dify symptom/medium -> 闸门覆盖 urgent。"""
    mock_client = _setup_fake_dify(
        monkeypatch,
        {"scene": "symptom", "risk_level": "medium", "confidence": 0.8, "payload": {"riskLevel": "medium"}},
    )
    with patch("health_consult.dify_proxy.get_dify_client", return_value=mock_client):
        result = asyncio.run(
            chat_with_dify(text="", answers={"red_swollen_hot": "yes"}, language="中文")
        )
    assert result["risk_level"] == "urgent"
    assert result["payload"]["solutionRef"] == "urgent_v1"


def test_urgent_gate_answers_fever_chills(monkeypatch):
    """空文本 + fever_chills=yes + Dify symptom/medium -> urgent。"""
    mock_client = _setup_fake_dify(
        monkeypatch,
        {"scene": "symptom", "risk_level": "medium", "confidence": 0.8, "payload": {}},
    )
    with patch("health_consult.dify_proxy.get_dify_client", return_value=mock_client):
        result = asyncio.run(
            chat_with_dify(text="", answers={"fever_chills": "yes"}, language="中文")
        )
    assert result["risk_level"] == "urgent"


def test_urgent_gate_answers_calf_swelling(monkeypatch):
    """空文本 + calf_swelling=yes + Dify symptom/medium -> urgent。"""
    mock_client = _setup_fake_dify(
        monkeypatch,
        {"scene": "symptom", "risk_level": "medium", "confidence": 0.8, "payload": {}},
    )
    with patch("health_consult.dify_proxy.get_dify_client", return_value=mock_client):
        result = asyncio.run(
            chat_with_dify(text="", answers={"calf_swelling": "yes"}, language="中文")
        )
    assert result["risk_level"] == "urgent"


def test_urgent_gate_no_urgent_answers_keeps_medium(monkeypatch):
    """空文本 + 无危险信号答案 + Dify medium -> 不覆盖, 保持 medium (闸门不误伤)。"""
    mock_client = _setup_fake_dify(
        monkeypatch,
        {"scene": "symptom", "risk_level": "medium", "confidence": 0.8, "payload": {"riskLevel": "medium"}},
    )
    with patch("health_consult.dify_proxy.get_dify_client", return_value=mock_client):
        result = asyncio.run(
            chat_with_dify(text="", answers={"location": "knee", "trigger": "stairs"}, language="中文")
        )
    assert result["risk_level"] == "medium"


def test_detect_urgent_answers_covers_all_seven_keys():
    """复审 P1: 工作流 URGENT_ANSWER_KEYS 缺的 3 个 key 后端必须覆盖。"""
    from health_consult.scene_router import detect_urgent_answers
    # leg_pain 量表全部 7 个 urgent 问题(含工作流漏的 red_swollen_hot/calf_swelling/fever_chills)
    urgent_qids = [
        "sudden_severe", "trauma", "cannot_stand", "red_swollen_hot",
        "calf_swelling", "chest_discomfort", "fever_chills",
    ]
    for qid in urgent_qids:
        assert detect_urgent_answers({qid: "yes"}) is True, f"{qid}=yes 应判 urgent"
    # 非危险信号答案不触发
    assert detect_urgent_answers({"red_swollen_hot": "no"}) is False
    assert detect_urgent_answers({"location": "knee"}) is False
    assert detect_urgent_answers({}) is False
    assert detect_urgent_answers(None) is False
