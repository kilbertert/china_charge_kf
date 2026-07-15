"""End-to-end verifier: POST test cases to a deployed Dify workflow
(via SSH + curl) and compare the returned scene/risk_level/fields to
expectations.

Two test modes are supported:

  1. **Inline code test** — runs a Code node's Python source against
     mock LLM output. This is what we use to validate the safety-net
     logic before paying for an LLM round-trip.

  2. **Live HTTP test** — POSTs multipart form-data to a Dify workflow
     endpoint and inspects the JSON response.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from dify_workflow_toolkit.ssh_client import SSHClient


@dataclass
class TestCase:
    """A single end-to-end test case.

    Attributes:
        case_id: short identifier used in test output
        text: the user text to send (may be empty)
        has_image: whether to attach a dummy image field
        answers: pre-filled questionnaire answers (JSON string)
        expected: dict of expected fields. Each field is checked with
            a deep equality (any nested dict/list), except keys that
            start with `_` (which are ignored).
        endpoint: optional override for the chat endpoint URL
        session_id: optional override
        description: human-readable description
    """

    case_id: str
    expected: dict[str, Any]
    text: str = ""
    has_image: bool = False
    answers: str = ""
    endpoint: str | None = None
    session_id: str | None = None
    description: str = ""


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    actual: dict[str, Any]
    expected: dict[str, Any]
    mismatches: list[str] = field(default_factory=list)
    description: str = ""
    error: str | None = None


@dataclass
class VerificationReport:
    total: int
    passed: int
    failed: int
    results: list[CaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total) if self.total else 0.0

    def __str__(self) -> str:
        return f"VerificationReport {self.passed}/{self.total} passed ({self.pass_rate:.0%})"


def _compare(actual: Any, expected: Any, *, path: str = "") -> list[str]:
    """Compare actual vs expected, return list of human-readable diffs.

    Special cases:
      - if `expected` is a string starting with `>=`, parse the
        rest as float and require `actual >= N` (for confidence checks)
      - if `expected` is a string starting with `<=`, parse float and
        require `actual <= N`
      - if `expected` is a string starting with `~` (regex), match
        `actual` against the pattern
    """
    diffs: list[str] = []
    if isinstance(expected, str) and expected.startswith(">="):
        try:
            threshold = float(expected[2:])
        except ValueError:
            threshold = 0.0
        if not (isinstance(actual, (int, float)) and actual >= threshold):
            diffs.append(f"{path}: {actual!r} (expected >= {threshold})")
        return diffs
    if isinstance(expected, str) and expected.startswith("<="):
        try:
            threshold = float(expected[2:])
        except ValueError:
            threshold = 0.0
        if not (isinstance(actual, (int, float)) and actual <= threshold):
            diffs.append(f"{path}: {actual!r} (expected <= {threshold})")
        return diffs
    if isinstance(expected, str) and expected.startswith("~"):
        pattern = expected[1:]
        if not (isinstance(actual, str) and re.search(pattern, actual)):
            diffs.append(f"{path}: {actual!r} (expected ~/{pattern}/)")
        return diffs
    if isinstance(expected, dict) and isinstance(actual, dict):
        for k, v in expected.items():
            if k.startswith("_"):
                continue
            sub = f"{path}.{k}" if path else k
            if k not in actual:
                diffs.append(f"{sub}: missing (actual has no key)")
            else:
                diffs.extend(_compare(actual[k], v, path=sub))
        return diffs
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            diffs.append(f"{path}: list length {len(actual)} != expected {len(expected)}")
        for i, (a, e) in enumerate(zip(actual, expected)):
            diffs.extend(_compare(a, e, path=f"{path}[{i}]"))
        return diffs
    if actual != expected:
        diffs.append(f"{path}: {actual!r} != expected {expected!r}")
    return diffs


def run_code_test(
    code: str,
    *,
    inputs: dict[str, Any],
    llm_text: str = "",
) -> dict[str, Any]:
    """Execute a Dify Code node's Python `main()` with given inputs.

    `inputs` keys are passed as kwargs to `main(llm_text=..., text=...,
    has_image=..., answers=...)`. Use this for offline unit testing of
    the code safety-net logic.
    """
    namespace: dict[str, Any] = {"__builtins__": __builtins__}
    exec(code, namespace)
    main_fn = namespace["main"]
    payload = {"llm_text": llm_text, **inputs}
    return main_fn(**payload)


class Verifier:
    """Run test cases against a deployed workflow endpoint.

    The endpoint is hit over SSH (so we hit the Dify host directly,
    avoiding network egress through a jump box).
    """

    def __init__(
        self,
        ssh: SSHClient,
        *,
        default_endpoint: str = "http://127.0.0.1:8013/api/health-consult/chat",
        curl_timeout: int = 60,
    ) -> None:
        self.ssh = ssh
        self.default_endpoint = default_endpoint
        self.curl_timeout = curl_timeout

    def run(self, cases: Sequence[TestCase]) -> VerificationReport:
        results: list[CaseResult] = []
        for case in cases:
            results.append(self._run_one(case))
        passed = sum(1 for r in results if r.passed)
        return VerificationReport(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    def _run_one(self, case: TestCase) -> CaseResult:
        endpoint = case.endpoint or self.default_endpoint
        session_id = case.session_id or f"verify-{case.case_id}-{int(time.time())}"
        parts = [f"curl -s -m {self.curl_timeout} -X POST '{endpoint}'"]
        parts.append(f"--data-urlencode 'text={case.text}'")
        parts.append(f"--data-urlencode 'session_id={session_id}'")
        if case.answers:
            parts.append(f"--data-urlencode 'answers={case.answers}'")
        if case.has_image:
            parts.append("-F 'image=@/dev/null'")
        cmd = " ".join(parts)
        out, _, rc = self.ssh.run(cmd, timeout=self.curl_timeout + 10)
        if rc != 0:
            return CaseResult(
                case_id=case.case_id,
                passed=False,
                actual={},
                expected=case.expected,
                description=case.description,
                error=f"curl rc={rc}: {out[:300]}",
            )
        body = self._extract_json(out)
        if body is None:
            return CaseResult(
                case_id=case.case_id,
                passed=False,
                actual={"_raw": out[:500]},
                expected=case.expected,
                description=case.description,
                error="could not parse JSON from response",
            )
        mismatches = _compare(body, case.expected)
        return CaseResult(
            case_id=case.case_id,
            passed=not mismatches,
            actual=body,
            expected=case.expected,
            mismatches=mismatches,
            description=case.description,
        )

    @staticmethod
    def _extract_json(out: str) -> dict[str, Any] | None:
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            pass
        start = out.find("{")
        end = out.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(out[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def format_report(report: VerificationReport) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(str(report))
    lines.append("=" * 70)
    for r in report.results:
        flag = "OK" if r.passed else "FAIL"
        desc = f" -- {r.description}" if r.description else ""
        lines.append(f"  [{flag}] {r.case_id}{desc}")
        if not r.passed:
            for m in r.mismatches:
                lines.append(f"        {m}")
            if r.error:
                lines.append(f"        error: {r.error}")
    lines.append("=" * 70)
    return "\n".join(lines)


def run_test_cases(
    ssh: SSHClient,
    cases: Sequence[TestCase],
    *,
    endpoint: str | None = None,
) -> VerificationReport:
    """Shorthand: Verifier().run() + print."""
    v = Verifier(ssh, default_endpoint=endpoint or "http://127.0.0.1:8013/api/health-consult/chat")
    report = v.run(cases)
    print(format_report(report))
    return report
