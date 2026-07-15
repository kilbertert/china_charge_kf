#!/usr/bin/env python3
"""
Deploy scene_classifier_v2 (LLM+code hybrid) to Dify.

The user did not have SSH access during this session, so this script is
left for manual execution. It:
  1. Reads the local AI_health_consultant_v2.yml
  2. Connects to the Dify Postgres (running inside the api-1 container)
  3. Updates the `workflows` row where app_id = '<health_consult_app_id>'
     and version != 'draft' (the published version worker reads)
  4. Verifies the update by SELECT LENGTH(graph)
  5. (Optionally) restarts the Dify api + worker containers

Usage:
  # Inside the Dify api-1 container:
  python scripts/deploy_v2_scene_classifier.py
  python scripts/deploy_v2_scene_classifier.py --app-id d2623d9a-ac8e-40b6-9ba8-ded2f99f874a
  python scripts/deploy_v2_scene_classifier.py --restart  # also restart containers

Prerequisites (must be set inside the Dify api-1 container):
  - Python 3 with psycopg2 installed:  pip install psycopg2-binary
  - The yml file present at:
      /root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/AI_health_consultant_v2.yml
  - DB env vars (auto-set by docker compose): DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
import yaml

# Health consult app_id (from previous session)
DEFAULT_APP_ID = "d2623d9a-ac8e-40b6-9ba8-ded2f99f874a"
YML_PATH = Path("/root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/AI_health_consultant_v2.yml")


def load_yml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_published_workflows(cur, app_id: str) -> list:
    cur.execute(
        """
        SELECT id, version, LENGTH(graph::text) AS graph_len
        FROM workflows
        WHERE app_id = %s
        ORDER BY updated_at DESC
        """,
        (app_id,),
    )
    return [
        {"id": r[0], "version": str(r[1]), "graph_len": r[2]}
        for r in cur.fetchall()
    ]


def update_published_graph(cur, app_id: str, new_graph: dict) -> int:
    graph_json = json.dumps(new_graph, ensure_ascii=False)
    cur.execute(
        """
        UPDATE workflows
        SET graph = %s::jsonb,
            updated_at = NOW()
        WHERE app_id = %s
          AND version != 'draft'
        """,
        (graph_json, app_id),
    )
    return cur.rowcount


def restart_dify_containers() -> None:
    for ctr in ("docker-api-1", "docker-worker-1", "docker-worker-beat-1"):
        try:
            subprocess.run(
                ["docker", "restart", ctr],
                check=True, capture_output=True, text=True,
            )
            print(f"  restarted {ctr}")
        except subprocess.CalledProcessError as e:
            print(f"  [warn] failed to restart {ctr}: {e.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", default=DEFAULT_APP_ID)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"[1/5] Loading yml from {YML_PATH}...")
    if not YML_PATH.exists():
        print(f"  [error] yml not found: {YML_PATH}")
        return 1
    yml_data = load_yml(YML_PATH)
    graph = yml_data["workflow"]["graph"]
    nodes = graph["nodes"]
    edges = graph["edges"]
    print(f"  nodes={len(nodes)}, edges={len(edges)}")

    if not any(n.get("id") == "4080" for n in nodes):
        print(f"  [error] node 4080 (LLM scene_classifier) not found in yml")
        return 1
    print("  node 4080 (LLM scene_classifier) present")

    node_4002 = next((n for n in nodes if n.get("id") == "4002"), None)
    if not node_4002:
        print(f"  [error] node 4002 not found")
        return 1
    var_names = [v.get("variable") for v in node_4002["data"].get("variables", [])]
    if "llm_text" not in var_names:
        print(f"  [error] node 4002 missing 'llm_text' variable (got: {var_names})")
        return 1
    print("  node 4002 has 'llm_text' variable")

    print(f"[2/5] Connecting to Postgres...")
    db_host = os.environ.get("DB_HOST", "db")
    db_port = int(os.environ.get("DB_PORT", "5432"))
    db_user = os.environ.get("DB_USERNAME", "postgres")
    db_pass = os.environ.get("DB_PASSWORD", "")
    db_name = os.environ.get("DB_DATABASE", "dify")
    try:
        conn = psycopg2.connect(
            host=db_host, port=db_port, user=db_user, password=db_pass, dbname=db_name,
        )
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    except Exception as e:
        print(f"  [error] Postgres connect failed: {e}")
        print(f"  hint: run this script INSIDE docker-api-1 container")
        return 1

    try:
        print(f"[3/5] Listing workflows for app_id={args.app_id}...")
        workflows = get_published_workflows(cur, args.app_id)
        for w in workflows:
            print(f"  - id={w['id']} version={w['version']} graph_len={w['graph_len']}")
        if not workflows:
            print(f"  [error] no workflows found for app_id={args.app_id}")
            return 1
        published = [w for w in workflows if w["version"] != "draft"]
        if not published:
            print(f"  [error] no published (non-draft) workflow found")
            return 1
        if len(published) > 1:
            print(f"  [warn] {len(published)} published versions found, updating all")

        if args.dry_run:
            print(f"[4/5] DRY RUN: would update {len(published)} published workflows")
            print(f"[5/5] DRY RUN: would {'restart containers' if args.restart else 'skip restart'}")
            return 0

        print(f"[4/5] Updating published workflow graph...")
        rows = update_published_graph(cur, args.app_id, graph)
        conn.commit()
        print(f"  updated {rows} rows")
        if rows == 0:
            print(f"  [error] no rows updated, check app_id")
            return 1

        cur.execute(
            """
            SELECT id, version, LENGTH(graph::text) AS graph_len
            FROM workflows
            WHERE app_id = %s AND version != 'draft'
            """,
            (args.app_id,),
        )
        for r in cur.fetchall():
            print(f"  - id={r['id']} version={r['version']} graph_len={r['graph_len']}")

        print(f"[5/5] {'Restarting containers' if args.restart else 'Skipping restart'}")
        if args.restart:
            restart_dify_containers()
    finally:
        cur.close()
        conn.close()

    print()
    print("=" * 60)
    print("Deploy complete!")
    print("=" * 60)
    print("Test cases to verify (POST /api/health-consult/chat):")
    print("  1. text='我右小腿胀痛 腰间盘突出 压迫神经' -> scene=symptom")
    print("  2. text='补钙产品哪个好' -> scene=product")
    print("  3. text='我膝盖疼是怎么回事' -> scene=symptom")
    print("  4. text='你好' -> scene=symptom(confidence~0.3)")
    print("  5. text='我腿不疼' -> scene=symptom")
    print("  6. text='' + image -> scene=report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
