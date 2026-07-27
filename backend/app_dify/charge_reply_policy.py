"""Deterministic charge-customer-service reply and routing policy.

The generated ``shared/charge_service.yaml`` is the runtime authority for
verified business facts. The policy also keeps high-risk requests and obvious
Bug/progress routing out of the LLM path.
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

        routing = data.get("routing") or {}
        self._bug_terms = tuple(str(item).lower() for item in routing.get("bug_terms") or [])
        self._progress_terms = tuple(
            str(item).lower() for item in routing.get("progress_terms") or []
        )
        self._inability_terms = tuple(
            str(item).lower() for item in routing.get("inability_terms") or []
        )
        self._attachment_bug_terms = tuple(
            str(item).lower() for item in routing.get("attachment_bug_terms") or []
        )

        matchers = data.get("matchers") or {}
        self._billing_matchers = matchers.get("billing_templates") or {}
        self._fault_repair_matchers = matchers.get("user_fault_repair") or {}
        self._order_export_matchers = matchers.get("order_export") or {}

        knowledge = data.get("verified_knowledge") or {}
        self._billing = knowledge.get("billing_templates") or {}
        self._fault_repair = knowledge.get("user_fault_repair") or {}
        self._order_management = knowledge.get("order_management") or {}

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

    @staticmethod
    def _terms(config: dict[str, Any], key: str) -> tuple[str, ...]:
        return tuple(str(item).lower() for item in config.get(key) or [])

    @staticmethod
    def _has_any(query: str, terms: tuple[str, ...]) -> bool:
        return any(term in query for term in terms)

    def _reply(
        self,
        replies: dict[str, Any],
        key: str,
        language: str,
        route: str,
    ) -> PolicyReply | None:
        lang = self._language_key(language)
        reply = replies.get(f"{key}_{lang}") or replies.get(f"{key}_zh")
        return PolicyReply(str(reply), route) if reply else None

    def _fault_repair_response(self, text: str, language: str) -> PolicyReply | None:
        query = (text or "").lower()
        match_terms = self._terms(self._fault_repair_matchers, "match_terms")
        intent_terms = self._terms(self._fault_repair_matchers, "intent_terms")
        if not self._has_any(query, match_terms) or not self._has_any(query, intent_terms):
            return None
        return self._reply(
            self._fault_repair.get("replies") or {},
            "location",
            language,
            "verified_user_fault_repair",
        )

    def _billing_response(self, text: str, language: str) -> PolicyReply | None:
        query = (text or "").lower()
        match_terms = self._terms(self._billing_matchers, "match_terms")
        if not self._has_any(query, match_terms):
            return None

        replies = self._billing.get("replies") or {}
        intent_order = (
            ("replacement_terms", "replacement", "verified_billing_replacement"),
            ("activation_terms", "activation", "verified_billing_activation"),
            ("association_terms", "association", "verified_billing_association"),
            ("startup_balance_terms", "startup_balance", "verified_billing_startup_balance"),
            ("time_of_use_terms", "time_of_use", "verified_billing_time_of_use"),
            ("setup_terms", "setup", "verified_billing_setup"),
            ("location_terms", "location", "verified_billing_location"),
        )
        for term_key, reply_key, route in intent_order:
            if self._has_any(query, self._terms(self._billing_matchers, term_key)):
                return self._reply(replies, reply_key, language, route)

        # A billing-template query that is not covered by a verified intent is
        # stopped here instead of being allowed to invent fields or prerequisites.
        return self._reply(
            replies,
            "guarded",
            language,
            "verified_billing_guarded",
        )

    def _order_export_response(self, text: str, language: str) -> PolicyReply | None:
        query = (text or "").lower()
        match_terms = self._terms(self._order_export_matchers, "match_terms")
        order_terms = self._terms(self._order_export_matchers, "order_terms")
        if not self._has_any(query, match_terms) or not self._has_any(query, order_terms):
            return None
        return self._reply(
            self._order_management.get("replies") or {},
            "export",
            language,
            "verified_order_export",
        )

    def route_target(
        self,
        *,
        text: str,
        active_app: str,
        has_attachments: bool,
    ) -> str | None:
        """Return a deterministic app target for obvious Bug/progress input."""
        if active_app == "B":
            return None
        query = (text or "").strip().lower()
        if self._has_any(query, self._progress_terms):
            return "B"
        if self._has_any(query, self._bug_terms):
            return "B"
        capability_question = any(term in query for term in ("能不能", "可不可以", "是否可以"))
        if not capability_question and self._has_any(query, self._inability_terms):
            return "B"
        if has_attachments and self._has_any(query, self._attachment_bug_terms):
            return "B"
        return None

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
        if has_attachments:
            return None
        if response := self._fault_repair_response(text, language):
            return response
        if response := self._order_export_response(text, language):
            return response
        if response := self._billing_response(text, language):
            return response
        if active_app != "A":
            # A live B draft owns vague follow-ups. Do not let the H5-level
            # clarification counter override B's business state machine.
            return None
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
