"""Deterministic charge-customer-service reply policy.

The policy handles responses that must not depend on an LLM: credential and
privilege refusal, bounded vague-input clarification, and verified high-volume
FAQ facts. All customer-facing text and verified facts live in
``shared/charge_service.yaml``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    if configured := os.environ.get("CHARGE_SERVICE_YAML_PATH"):
        paths.append(Path(configured))
    paths.append(Path("/app/shared/charge_service.yaml"))
    paths.append(Path(__file__).resolve().parents[2] / "shared" / "charge_service.yaml")
    return paths


def _find_config() -> Path:
    for path in _candidate_paths():
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"charge_service.yaml not found; searched: {[str(path) for path in _candidate_paths()]}"
    )


@dataclass(frozen=True)
class PolicyReply:
    text: str
    route: str
    vague_count: int = 0
    vague_exhausted: bool = False


class ChargeReplyPolicy:
    def __init__(self, data: dict[str, Any]) -> None:
        security = data.get("security") or {}
        self._refuse_patterns = tuple(
            re.compile(pattern) for pattern in security.get("refuse_patterns") or []
        )
        self._security_reply = security.get("reply") or {}

        clarification = data.get("clarification") or {}
        self.max_prompts = int(clarification.get("max_prompts") or 2)
        self._vague_phrases = tuple(
            str(item).lower() for item in clarification.get("vague_phrases") or []
        )
        self._domain_terms = tuple(
            str(item).lower() for item in clarification.get("domain_terms") or []
        )
        self._clarification_prompts = clarification.get("prompts") or {}
        self._exhausted_reply = clarification.get("exhausted_reply") or {}

        knowledge = data.get("verified_knowledge") or {}
        self._billing = knowledge.get("billing_templates") or {}

    @staticmethod
    def _language_key(language: str) -> str:
        return "en" if (language or "").lower().startswith("en") else "zh"

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[\s，。！？、,.!?;；:：'\"“”‘’]+", "", (text or "").lower())

    def _security_response(self, text: str, language: str) -> PolicyReply | None:
        if any(pattern.search(text or "") for pattern in self._refuse_patterns):
            lang = self._language_key(language)
            reply = self._security_reply.get(lang) or self._security_reply.get("zh")
            return PolicyReply(str(reply), "security_refusal")
        return None

    def _billing_response(self, text: str, language: str) -> PolicyReply | None:
        query = (text or "").lower()
        match_terms = tuple(str(item).lower() for item in self._billing.get("match_terms") or [])
        if not any(term in query for term in match_terms):
            return None

        setup_terms = tuple(str(item).lower() for item in self._billing.get("setup_terms") or [])
        location_terms = tuple(str(item).lower() for item in self._billing.get("location_terms") or [])
        is_setup = any(term in query for term in setup_terms)
        is_location = any(term in query for term in location_terms)
        if not is_setup and not is_location:
            return None

        lang = self._language_key(language)
        replies = self._billing.get("replies") or {}
        if is_setup:
            key = f"setup_{lang}"
            route = "verified_billing_setup"
        else:
            holiday_terms = tuple(
                str(item).lower() for item in self._billing.get("holiday_terms") or []
            )
            prefix = "holiday_location" if any(term in query for term in holiday_terms) else "location"
            key = f"{prefix}_{lang}"
            route = f"verified_billing_{prefix}"
        reply = replies.get(key) or replies.get(key.rsplit("_", 1)[0] + "_zh")
        return PolicyReply(str(reply), route) if reply else None

    def _is_vague(self, text: str) -> bool:
        query = (text or "").strip().lower()
        normalized = self._normalize(query)
        if not normalized:
            return True
        if any(term in query for term in self._domain_terms):
            return False
        normalized_phrases = {self._normalize(item) for item in self._vague_phrases}
        if normalized in normalized_phrases:
            return True
        return len(normalized) <= 12 and any(
            self._normalize(item) in normalized for item in self._vague_phrases
        )

    def _vague_response(
        self,
        *,
        text: str,
        language: str,
        vague_count: int,
        vague_exhausted: bool,
    ) -> PolicyReply | None:
        if not self._is_vague(text):
            return None
        lang = self._language_key(language)
        if vague_exhausted or vague_count >= self.max_prompts:
            reply = self._exhausted_reply.get(lang) or self._exhausted_reply.get("zh")
            return PolicyReply(
                str(reply),
                "vague_exhausted",
                vague_count=self.max_prompts,
                vague_exhausted=True,
            )

        next_count = vague_count + 1
        prompts = self._clarification_prompts.get(lang) or self._clarification_prompts.get("zh") or []
        prompt = prompts[min(next_count - 1, len(prompts) - 1)]
        return PolicyReply(
            str(prompt),
            f"vague_prompt_{next_count}",
            vague_count=next_count,
            vague_exhausted=False,
        )

    def evaluate(
        self,
        *,
        text: str,
        language: str,
        active_app: str,
        has_attachments: bool,
        vague_count: int,
        vague_exhausted: bool,
    ) -> PolicyReply | None:
        if response := self._security_response(text, language):
            return response
        if active_app != "A" or has_attachments:
            return None
        if response := self._billing_response(text, language):
            return response
        return self._vague_response(
            text=text,
            language=language,
            vague_count=vague_count,
            vague_exhausted=vague_exhausted,
        )


@lru_cache(maxsize=1)
def get_charge_reply_policy() -> ChargeReplyPolicy:
    with _find_config().open(encoding="utf-8") as handle:
        return ChargeReplyPolicy(yaml.safe_load(handle) or {})
