#!/usr/bin/env python3
"""Align the health workflow graph with the shared H5 response contract.

The patch is intentionally narrow and idempotent:
* 4105 routes ``has_answers=true`` to the fixed-answer branch;
* 4021/4024 use the shared leg-pain questionnaire and canonical solution refs;
* 4011 emits the shared fixed report questionnaire;
* 4121 marks completed report analysis as ``report_done``.

For production, only the effective workflow referenced by ``apps.workflow_id``
and the draft workflow are changed. A JSON backup of both graphs is written
before commit so the transaction can be restored without touching old versions.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import pprint
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

APP_ID = "d5e87520-a838-4c72-92cc-8b00eaa81382"

SOLUTION_TAG_ALIASES = {
    "possible_nerve_related": "lumbar_radiculopathy",
    "joint_load_related": "knee_degeneration",
    "persistent_leg_pain": "muscle_strain",
    "soft_tissue_overuse": "muscle_strain",
    "possible_radicular_back_pain": "lumbar_radiculopathy",
    "chronic_back_pain": "lumbar_radiculopathy",
    "mechanical_back_pain": "muscle_strain",
    "inflammatory_joint_pattern": "gout_inflammatory",
    "load_related_joint_pain": "knee_degeneration",
    "nonspecific_joint_pain": "muscle_strain",
    "needs_offline_assessment": "muscle_strain",
    "generic_low_risk_symptom": "muscle_strain",
}


def _node(graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in graph.get("nodes", []):
        if str(node.get("id")) == node_id:
            return node
    raise RuntimeError(f"workflow node {node_id} not found")


def _shared_questions(shared_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = yaml.safe_load(shared_path.read_text(encoding="utf-8")) or {}
    questionnaires = {item["id"]: item for item in data.get("questionnaires", [])}
    bone = questionnaires["bone_density_v1"]
    leg = questionnaires["leg_pain_v1"]
    leg_for_workflow = {
        "intent": "leg_pain",
        "title": leg["title"],
        "questions": copy.deepcopy(leg["questions"]),
    }
    report_questions = []
    for question in bone["questions"]:
        report_questions.append(
            {
                "id": question["id"],
                "text": question["text"],
                "options": [
                    {"key": option["key"], "label": option["label"]}
                    for option in question["options"]
                ],
            }
        )
    return leg_for_workflow, report_questions


def _patch_urgent_keys(code: str) -> str:
    replacement = '''URGENT_ANSWER_KEYS = [
    "sudden_severe", "trauma", "cannot_stand", "red_swollen_hot",
    "calf_swelling", "chest_discomfort", "fever_chills", "weakness_numbness",
]'''
    return re.sub(
        r"URGENT_ANSWER_KEYS\s*=\s*\[[\s\S]*?\n\]",
        replacement,
        code,
        count=1,
    )


def _patch_symptom_code(code: str, leg_questions: dict[str, Any]) -> str:
    code = _patch_urgent_keys(code)
    marker = "\n\n\ndef _parse_answers"
    assignment = "\n\nQUESTIONNAIRES['leg_pain_v1'] = " + pprint.pformat(
        leg_questions, width=100, sort_dicts=False
    )
    if "QUESTIONNAIRES['leg_pain_v1'] =" not in code:
        if marker not in code:
            raise RuntimeError("4024 questionnaire insertion marker not found")
        code = code.replace(marker, assignment + marker, 1)
    else:
        code = re.sub(
            r"QUESTIONNAIRES\['leg_pain_v1'\]\s*=\s*\{[\s\S]*?\n\n\ndef _parse_answers",
            assignment + marker,
            code,
            count=1,
        )

    aliases = pprint.pformat(SOLUTION_TAG_ALIASES, width=100, sort_dicts=False)
    if "SOLUTION_TAG_ALIASES =" not in code:
        code = code.replace(
            "def _complete(intent, questionnaire_ref, tag, risk_level, department, conclusion, answers):",
            f"SOLUTION_TAG_ALIASES = {aliases}\n\n\ndef _complete(intent, questionnaire_ref, tag, risk_level, department, conclusion, answers):",
            1,
        )
    code = code.replace('"tag": tag,', '"tag": SOLUTION_TAG_ALIASES.get(tag, tag),', 1)
    if '"solutionRef":' not in code:
        code = code.replace(
            '"tag": SOLUTION_TAG_ALIASES.get(tag, tag),\n',
            '"tag": SOLUTION_TAG_ALIASES.get(tag, tag),\n'
            '        "solutionRef": f"{SOLUTION_TAG_ALIASES.get(tag, tag)}_v1",\n',
            1,
        )
    return code


def _patch_report_code(code: str, report_questions: list[dict[str, Any]]) -> str:
    start = code.find("def _fallback_questions():")
    end = code.find("\n\ndef _insufficient", start)
    if start < 0 or end < 0:
        raise RuntimeError("4011 fallback question function not found")
    rendered_questions = pprint.pformat(report_questions, width=100, sort_dicts=False)
    rendered_questions = rendered_questions.replace("\n", "\n    ")
    fixed = "def _fallback_questions():\n    return " + rendered_questions + "\n"
    code = code[:start] + fixed + code[end:]
    code = code.replace(
        "follow_up = _sanitize_questions(data.get(\"followUpQuestions\")) or _fallback_questions()",
        "follow_up = _fallback_questions()",
        1,
    )
    return code


def _patch_done_code(code: str) -> str:
    marker = '"payloadKind": "complete",'
    before, separator, after = code.rpartition(marker)
    if not separator:
        return code
    return before + '"payloadKind": "report_done",' + after


def mutate_graph(graph: dict[str, Any], leg_questions: dict[str, Any], report_questions: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(graph)

    node_4105 = _node(result, "4105")
    cases = node_4105.setdefault("data", {}).setdefault("cases", [])
    if not cases or not cases[0].get("conditions"):
        raise RuntimeError("4105 has no has_answers condition")
    condition = cases[0]["conditions"][0]
    condition["comparison_operator"] = "is"
    condition["varType"] = "boolean"
    condition["value"] = True
    condition["variable_selector"] = ["4104", "has_answers"]

    node_4021 = _node(result, "4021")
    node_4021["data"]["code"] = _patch_urgent_keys(node_4021["data"].get("code", ""))

    node_4024 = _node(result, "4024")
    node_4024["data"]["code"] = _patch_symptom_code(node_4024["data"].get("code", ""), leg_questions)

    node_4011 = _node(result, "4011")
    node_4011["data"]["code"] = _patch_report_code(node_4011["data"].get("code", ""), report_questions)

    node_4121 = _node(result, "4121")
    node_4121["data"]["code"] = _patch_done_code(node_4121["data"].get("code", ""))
    return result


def patch_source(source_path: Path, shared_path: Path) -> None:
    raw = source_path.read_bytes().decode("utf-8")
    source = yaml.safe_load(raw)
    graph = source["workflow"]["graph"]
    leg_questions, report_questions = _shared_questions(shared_path)
    mutated = mutate_graph(graph, leg_questions, report_questions)
    newline = "\r\n" if "\r\n" in raw else "\n"

    def replace_node_code(text: str, node_id: str, code: str) -> str:
        node_marker = f"id: '{node_id}'"
        node_id_pos = text.find(node_marker)
        if node_id_pos < 0:
            raise RuntimeError(f"source node {node_id} not found")
        line_start = text.rfind(newline, 0, node_id_pos) + len(newline)
        if text.startswith("    - id:", line_start):
            node_start = line_start
        else:
            node_start = max(
                text.rfind(f"{newline}    - data:", 0, node_id_pos),
                text.rfind(f"{newline}    - id:", 0, node_id_pos),
            )
        if node_start < 0:
            raise RuntimeError(f"source node {node_id} start not found")
        code_marker = "        code: |-"
        code_start = text.find(code_marker, node_start)
        if code_start < 0:
            raise RuntimeError(f"source node {node_id} code block not found")
        content_start = code_start + len(code_marker)
        boundary = re.search(
            rf"{re.escape(newline)}        (?:desc|code_language|outputs|selected|title|type|variables):",
            text[content_start:],
        )
        if not boundary:
            raise RuntimeError(f"source node {node_id} code block boundary not found")
        content_end = content_start + boundary.start()
        code_lines = newline.join("          " + line if line else "" for line in code.splitlines())
        replacement = code_marker + newline + code_lines
        return text[:code_start] + replacement + text[content_end:]

    for node_id in ("4021", "4024", "4011", "4121"):
        node = _node(mutated, node_id)
        raw = replace_node_code(raw, node_id, node["data"]["code"])
    source_path.write_bytes(raw.encode("utf-8"))


def _connect_db():
    import psycopg2

    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )


def patch_database(
    source_path: Path,
    shared_path: Path,
    backup_path: Path,
    apply: bool,
) -> None:
    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    source_graph = source["workflow"]["graph"]
    if not shared_path.exists():
        raise RuntimeError(f"shared compliance file not found: {shared_path}")
    leg_questions, report_questions = _shared_questions(shared_path)
    import psycopg2.extras

    conn = _connect_db()
    backups = []
    changes = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT workflow_id FROM apps WHERE id=%s", (APP_ID,))
            effective = cur.fetchone()
            if not effective or not effective["workflow_id"]:
                raise RuntimeError("health app has no effective workflow")
            cur.execute("SELECT id FROM workflows WHERE app_id=%s AND version='draft'", (APP_ID,))
            draft = cur.fetchone()
            targets = [(str(effective["workflow_id"]), "effective")]
            if draft and str(draft["id"]) != targets[0][0]:
                targets.append((str(draft["id"]), "draft"))

            for workflow_id, kind in targets:
                cur.execute("SELECT id, version, graph FROM workflows WHERE id=%s FOR UPDATE", (workflow_id,))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError(f"workflow {workflow_id} not found")
                before = json.loads(row["graph"]) if isinstance(row["graph"], str) else row["graph"]
                after = mutate_graph(before, leg_questions, report_questions)
                backups.append({"workflow_id": workflow_id, "kind": kind, "version": str(row["version"]), "graph": before})
                changed = before != after
                changes.append({"workflow_id": workflow_id, "kind": kind, "changed": changed})
                if apply and changed:
                    cur.execute("UPDATE workflows SET graph=%s, updated_at=NOW() WHERE id=%s", (json.dumps(after, ensure_ascii=False), workflow_id))
            if apply:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                backup_path.write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "backups": backups}, ensure_ascii=False), encoding="utf-8")
                conn.commit()
            else:
                conn.rollback()
    finally:
        conn.close()
    print(json.dumps({"apply": apply, "changes": changes, "backup": str(backup_path) if apply else None}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--shared", type=Path)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-path", type=Path, default=Path("/app/api/storage/health-workflow-contract-backup.json"))
    args = parser.parse_args()

    if args.source_only:
        if not args.shared:
            parser.error("--shared is required with --source-only")
        patch_source(args.source, args.shared)
        print(json.dumps({"source": str(args.source), "patched": True}, ensure_ascii=False))
        return
    if not args.shared:
        parser.error("--shared is required")
    patch_database(args.source, args.shared, args.backup_path, args.apply)


if __name__ == "__main__":
    main()
