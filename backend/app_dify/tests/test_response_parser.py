"""Tests for app_dify.response_parser.

Run from the backend/ directory:
    cd backend && python -m pytest app_dify/tests -q
"""

from __future__ import annotations

import pytest

from app_dify.response_parser import (
    _classify_url,
    _media_from_text,
    _normalize_media_item,
    _safe_url,
    _strip_media_urls,
    extract_assistant_text_and_media,
    extract_structured_payload,
)


# ---------------------------------------------------------------------------
# _classify_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://cdn.example.com/img/photo.jpg", "image"),
        ("https://cdn.example.com/img/photo.jpeg", "image"),
        ("https://cdn.example.com/img/photo.PNG", "image"),
        ("https://cdn.example.com/img/photo.webp", "image"),
        ("https://cdn.example.com/videos/demo.mp4", "video"),
        ("https://cdn.example.com/videos/demo.MOV", "video"),
        ("https://cdn.example.com/files/notes.pdf", None),
        ("https://cdn.example.com/img/photo", None),
        ("not a url", None),
    ],
)
def test_classify_url(url: str, expected: str | None) -> None:
    assert _classify_url(url) == expected


# ---------------------------------------------------------------------------
# _safe_url — scheme / trailing-punct defense
# ---------------------------------------------------------------------------

def test_safe_url_accepts_http() -> None:
    assert _safe_url("http://x.com/a.jpg") == "http://x.com/a.jpg"


def test_safe_url_accepts_https() -> None:
    assert _safe_url("https://x.com/a.jpg") == "https://x.com/a.jpg"


def test_safe_url_strips_trailing_punctuation() -> None:
    # Final punctuation should not make it into the URL field.
    assert _safe_url("请看 https://x.com/a.mp4，谢谢。") == "https://x.com/a.mp4"


def test_safe_url_strips_trailing_closing_bracket() -> None:
    assert _safe_url("参考 (https://x.com/a.mp4)") == "https://x.com/a.mp4"


def test_safe_url_rejects_javascript_scheme() -> None:
    assert _safe_url("javascript:alert(1)") is None


def test_safe_url_rejects_data_scheme() -> None:
    assert _safe_url("data:image/png;base64,AAAA") is None


def test_safe_url_rejects_empty_or_non_string() -> None:
    assert _safe_url("") is None
    assert _safe_url(None) is None  # type: ignore[arg-type]
    assert _safe_url(123) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _normalize_media_item
# ---------------------------------------------------------------------------

def test_normalize_accepts_explicit_image() -> None:
    out = _normalize_media_item(
        {"type": "image", "url": "https://x.com/a.jpg", "description": "封面"}
    )
    assert out == {"type": "image", "url": "https://x.com/a.jpg", "description": "封面"}


def test_normalize_classifies_by_extension_when_type_missing() -> None:
    out = _normalize_media_item({"url": "https://x.com/a.mp4"})
    assert out is not None
    assert out["type"] == "video"
    assert out["description"] is None


def test_normalize_rejects_unsafe_url() -> None:
    assert _normalize_media_item({"type": "image", "url": "javascript:alert(1)"}) is None


def test_normalize_rejects_unknown_extension() -> None:
    assert _normalize_media_item({"type": "image", "url": "https://x.com/a.pdf"}) is None


def test_normalize_rejects_non_dict() -> None:
    assert _normalize_media_item("https://x.com/a.jpg") is None  # type: ignore[arg-type]
    assert _normalize_media_item(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _media_from_text
# ---------------------------------------------------------------------------

def test_media_from_text_finds_image_and_video() -> None:
    text = "请看图片 https://x.com/a.png 和视频 https://x.com/b.mp4 谢谢"
    out = _media_from_text(text)
    assert len(out) == 2
    assert {"url": "https://x.com/a.png", "type": "image", "description": None} in out
    assert {"url": "https://x.com/b.mp4", "type": "video", "description": None} in out


def test_media_from_text_dedupes() -> None:
    text = "https://x.com/a.png 看一次 https://x.com/a.png 再看一次"
    out = _media_from_text(text)
    assert len(out) == 1


def test_media_from_text_ignores_non_media_urls() -> None:
    text = "详情见 https://x.com/help.html"
    assert _media_from_text(text) == []


# ---------------------------------------------------------------------------
# _strip_media_urls
# ---------------------------------------------------------------------------

def test_strip_media_urls_removes_and_collapses() -> None:
    text = "先看视频 https://x.com/a.mp4   然后看图 https://x.com/b.png"
    out = _strip_media_urls(text, ["https://x.com/a.mp4", "https://x.com/b.png"])
    # The two URLs leave behind "先看视频    然后看图" → collapsed to single spaces.
    assert "https://" not in out
    assert "先看视频" in out and "然后看图" in out


# ---------------------------------------------------------------------------
# extract_structured_payload
# ---------------------------------------------------------------------------

def test_extract_structured_payload_parses_plain_json() -> None:
    raw = {
        "data": {
            "outputs": {
                "output": '{"text": "你好", "media": [{"type": "image", "url": "https://x.com/a.jpg"}]}'
            }
        }
    }
    parsed = extract_structured_payload(raw, "output")
    assert parsed == {
        "text": "你好",
        "media": [{"type": "image", "url": "https://x.com/a.jpg"}],
    }


def test_extract_structured_payload_strips_fences() -> None:
    raw = {
        "data": {
            "outputs": {
                "output": '```json\n{"text": "ok", "media": []}\n```'
            }
        }
    }
    parsed = extract_structured_payload(raw, "output")
    assert parsed == {"text": "ok", "media": []}


def test_extract_structured_payload_strips_thinking() -> None:
    raw = {
        "data": {
            "outputs": {
                "output": '<think>reasoning</think>{"text": "ok", "media": []}'
            }
        }
    }
    parsed = extract_structured_payload(raw, "output")
    assert parsed == {"text": "ok", "media": []}


def test_extract_structured_payload_returns_none_for_non_json() -> None:
    raw = {"data": {"outputs": {"output": "纯文本回答"}}}
    assert extract_structured_payload(raw, "output") is None


def test_extract_structured_payload_returns_none_for_empty() -> None:
    assert extract_structured_payload({}, "output") is None
    assert extract_structured_payload(None, "output") is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# extract_assistant_text_and_media — JSON path
# ---------------------------------------------------------------------------

def test_text_and_media_json_path() -> None:
    raw = {
        "data": {
            "outputs": {
                "output": (
                    '{"text": "操作步骤如下",'
                    ' "media": ['
                    '  {"type": "video", "url": "https://x.com/v.mp4", "description": "演示"}'
                    ']}'
                )
            }
        }
    }
    text, media = extract_assistant_text_and_media(raw)
    assert text == "操作步骤如下"
    assert media == [
        {"type": "video", "url": "https://x.com/v.mp4", "description": "演示"}
    ]


def test_text_and_media_json_path_filters_unsafe_url() -> None:
    raw = {
        "data": {
            "outputs": {
                "output": json_dumps(
                    {"text": "x", "media": [{"type": "image", "url": "javascript:alert(1)"}]}
                )
            }
        }
    }
    text, media = extract_assistant_text_and_media(raw)
    assert text == "x"
    assert media == []


def test_text_and_media_json_with_inline_url_falls_back_to_regex() -> None:
    # LLM gives JSON with empty media array but pastes the URL in text body.
    raw = {
        "data": {
            "outputs": {
                "output": '{"text": "看 https://x.com/a.mp4", "media": []}'
            }
        }
    }
    text, media = extract_assistant_text_and_media(raw)
    assert media == [{"type": "video", "url": "https://x.com/a.mp4", "description": None}]
    assert "https://" not in text
    assert "看" in text


# ---------------------------------------------------------------------------
# extract_assistant_text_and_media — regex fallback path
# ---------------------------------------------------------------------------

def test_text_and_media_regex_fallback_strips_url_from_text() -> None:
    raw = {
        "data": {
            "outputs": {
                "output": "请看视频 https://x.com/a.mp4 谢谢"
            }
        }
    }
    text, media = extract_assistant_text_and_media(raw)
    assert media == [{"type": "video", "url": "https://x.com/a.mp4", "description": None}]
    assert "https://" not in text


def test_text_and_media_no_media_returns_empty_list() -> None:
    raw = {"data": {"outputs": {"output": "纯文本回答,没有媒体"}}}
    text, media = extract_assistant_text_and_media(raw)
    assert text == "纯文本回答,没有媒体"
    assert media == []


def test_text_and_media_empty_raw_returns_empty_string_and_list() -> None:
    text, media = extract_assistant_text_and_media({})
    # Falls back to the debug pretty-print path which returns '{}'.
    assert isinstance(text, str)
    assert media == []


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def json_dumps(obj: object) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
