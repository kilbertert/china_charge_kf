from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

# Strip reasoning blocks leaked by thinking-enabled models (e.g. doubao-seed-2-0-lite).
# Matched non-greedy with DOTALL so multi-line / empty <think>\n\n</think> cases are handled.
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    if not text:
        return ""
    return _THINK_BLOCK_RE.sub("", text).strip()


def _first_nonempty_string(value: Any, depth: int = 0) -> str | None:
    if depth >= 8:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, dict):
        for v in value.values():
            found = _first_nonempty_string(v, depth + 1)
            if found:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            found = _first_nonempty_string(item, depth + 1)
            if found:
                return found
        return None
    return None


def extract_assistant_text(raw: dict, preferred_key: str = "output") -> str:
    """
    Pull the user-facing reply out of a Dify workflow blocking response.

    Dify structure is regular:
        raw["data"]["outputs"][<var_name>] = <text>

    We still fall back to a deep search because some workflows dump the entire
    answer into a single generic key like "result"/"text"/"answer".

    Reasoning blocks (<think>...</think>) leaked by thinking-enabled models are
    stripped before returning, so the frontend never sees chain-of-thought.
    """
    data = (raw or {}).get("data") or {}
    outputs = data.get("outputs") or {}

    # 1) Preferred key (configurable via dify_output_text, default "output")
    text = _strip_thinking(_first_nonempty_string(outputs.get(preferred_key)) or "")
    if text:
        return text

    # 2) Common fallbacks
    for k in ("output", "answer", "result", "text", "message", "content"):
        text = _strip_thinking(_first_nonempty_string(outputs.get(k)) or "")
        if text:
            return text

    # 3) Deep search across outputs
    text = _strip_thinking(_first_nonempty_string(outputs) or "")
    if text:
        return text

    # 4) Last resort: pretty-print the raw for debug visibility
    try:
        return json.dumps(raw, ensure_ascii=False, indent=2)
    except Exception:
        return str(raw)


# ----------------------------------------------------------------------
# Media extraction (new — supports image / video in assistant replies)
# ----------------------------------------------------------------------

_IMAGE_EXT = ("jpg", "jpeg", "png", "gif", "webp", "bmp", "svg")
_VIDEO_EXT = ("mp4", "mov", "webm", "m4v", "avi", "mkv")
_IMAGE_SET = set(_IMAGE_EXT)
_VIDEO_SET = set(_VIDEO_EXT)

# Match http(s) URLs ending in one of the known media extensions. Excludes
# characters that typically delimit a URL in prose (``<>"\`'){}``) so we don't
# grab punctuation or surrounding quote pairs.
_MEDIA_URL_RE = re.compile(
    r"https?://[^\s<>\"'\)\}\]]+\.("
    + "|".join(_IMAGE_EXT + _VIDEO_EXT)
    + r")(?:\?[^\s<>\"'\)\}\]]*)?",
    re.IGNORECASE,
)

# Trailing punctuation that frequently clings to URLs in prose; we strip them
# post-match so they don't end up in the URL field of MediaItem. Includes
# Chinese full-width punctuation because the regex doesn't exclude it and
# LLMs (or surrounding prose) often tack them on.
_TRAILING_CHARS = ".,;:!?)]}。,;:!?·…\"'"


def _safe_url(url: str) -> str | None:
    """Validate the URL scheme is http(s); return a cleaned URL or None.

    Accepts either a clean URL or a string with surrounding prose / trailing
    punctuation (Chinese or ASCII); in the latter case, the URL is found via
    ``_MEDIA_URL_RE`` and then scheme-validated. Defends against
    javascript:/data:/vbscript:/file: schemes.
    """
    if not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    # Strip common trailing prose punctuation / bracket noise.
    while s and s[-1] in _TRAILING_CHARS:
        s = s[:-1]
    if not s:
        return None
    # If the cleaned string itself isn't a valid http(s) URL, try to find a
    # media URL inside it (handles "请看 https://x.com/a.mp4，谢谢。").
    try:
        parsed = urlparse(s)
    except ValueError:
        parsed = None
    if parsed is None or parsed.scheme not in ("http", "https") or not parsed.netloc:
        for m in _MEDIA_URL_RE.finditer(s):
            candidate = _safe_url(m.group(0))
            if candidate:
                return candidate
        return None
    return s


def _classify_url(url: str) -> str | None:
    """Map a URL to ``"image"`` / ``"video"`` based on extension. Unknown → None."""
    try:
        path = urlparse(url).path.lower()
    except ValueError:
        return None
    if "." not in path:
        return None
    ext = path.rsplit(".", 1)[-1]
    if ext in _IMAGE_SET:
        return "image"
    if ext in _VIDEO_SET:
        return "video"
    return None


def _strip_media_urls(text: str, urls: list[str]) -> str:
    """Remove `urls` substrings from `text` and collapse leftover whitespace.

    Used by the regex-fallback path so the frontend doesn't display the raw
    URL twice (once in text, once inside the media bubble).
    """
    if not text or not urls:
        return text
    for u in urls:
        text = text.replace(u, "")
    # Collapse multiple spaces / blank lines created by URL removal.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _try_parse_json(text: str) -> dict | None:
    """Parse `text` as JSON, with a small cleanup for ```json fences."""
    if not text:
        return None
    s = _strip_thinking(text)
    if not s:
        return None
    # Strip leading/trailing markdown code fences like ```json ... ```.
    s = _FENCE_RE.sub("", s).strip()
    if not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_media_item(item: Any) -> dict | None:
    """Coerce a single media entry (from JSON or regex) to a valid MediaItem dict.

    Returns None for entries with missing / invalid url or type that doesn't
    match the URL's extension. The type/extension cross-check is intentional:
    it stops a hostile or hallucinated LLM from sneaking a ``.pdf`` past as an
    ``image``, etc.
    """
    if not isinstance(item, dict):
        return None
    url_raw = item.get("url")
    url = _safe_url(url_raw) if isinstance(url_raw, str) else None
    if not url:
        return None
    type_raw = item.get("type")
    declared: str | None = type_raw if type_raw in ("image", "video") else None
    classified = _classify_url(url)
    # Reject if declared type contradicts the URL extension, or if the
    # extension is unknown (so we can't cross-check the LLM's claim).
    if classified and declared and classified != declared:
        return None
    if classified in ("image", "video"):
        type_norm: str | None = classified
    else:
        # No usable extension classification — refuse to guess.
        type_norm = None
    if type_norm not in ("image", "video"):
        return None
    description = item.get("description")
    if not isinstance(description, str) or not description.strip():
        description = None
    return {"type": type_norm, "url": url, "description": description}


def _media_from_json(parsed: dict) -> list[dict]:
    raw_media = parsed.get("media")
    if not isinstance(raw_media, list):
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for entry in raw_media:
        norm = _normalize_media_item(entry)
        if not norm:
            continue
        if norm["url"] in seen:
            continue
        seen.add(norm["url"])
        out.append(norm)
    return out


def _media_from_text(text: str) -> list[dict]:
    """Regex fallback: pull media URLs out of free-form text and classify by ext."""
    if not text:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for match in _MEDIA_URL_RE.finditer(text):
        candidate = _safe_url(match.group(0))
        if not candidate or candidate in seen:
            continue
        kind = _classify_url(candidate)
        if not kind:
            continue
        seen.add(candidate)
        out.append({"type": kind, "url": candidate, "description": None})
    return out


def extract_structured_payload(raw: dict, preferred_key: str) -> dict | None:
    """Try to read a JSON ``{text, media}`` payload out of the workflow output.

    Looks at ``raw["data"]["outputs"][preferred_key]`` first, then falls back to
    the same preferred/common keys ``extract_assistant_text`` uses. Returns
    the parsed dict, or None if no key yielded parseable JSON.
    """
    outputs = ((raw or {}).get("data") or {}).get("outputs") or {}
    candidate_keys = [preferred_key, "output", "answer", "result", "text", "message", "content"]
    seen: set[str] = set()
    for k in candidate_keys:
        if k in seen:
            continue
        seen.add(k)
        raw_val = outputs.get(k)
        if not isinstance(raw_val, str):
            continue
        parsed = _try_parse_json(raw_val)
        if parsed is not None:
            return parsed
    return None


def extract_assistant_text_and_media(
    raw: dict, preferred_key: str = "output"
) -> tuple[str, list[dict]]:
    """Unified entry point returning ``(assistant_text, media_list)``.

    Strategy:
      1. If the workflow output is a JSON ``{text, media:[…]}`` blob, use it
         directly and validate every media entry through ``_normalize_media_item``
         (which enforces the http(s) scheme and the image/video type).
      2. Otherwise fall back to ``extract_assistant_text`` for the text, and
         scan that text with ``_MEDIA_URL_RE`` for media URLs. The same URLs
         are stripped from the returned text so the frontend never shows them
         twice.
      3. <think>…</think> blocks are stripped in both paths (via
         ``_strip_thinking`` / ``_try_parse_json``).
    """
    parsed = extract_structured_payload(raw, preferred_key)

    if parsed is not None and ("text" in parsed or "media" in parsed):
        text_raw = parsed.get("text")
        if not isinstance(text_raw, str):
            text_raw = ""
        text = _strip_thinking(text_raw) or ""
        media = _media_from_json(parsed)
        # If the JSON had no media, still mine the text body for embedded URLs
        # — LLM sometimes omits the media array but pastes the URL inline.
        if not media:
            media = _media_from_text(text)
            if media:
                text = _strip_media_urls(text, [m["url"] for m in media])
        return text, media

    # ---- Fallback: free-form text ----
    text = extract_assistant_text(raw, preferred_key=preferred_key)
    text = _strip_thinking(text)
    media = _media_from_text(text)
    if media:
        text = _strip_media_urls(text, [m["url"] for m in media])
    return text, media
