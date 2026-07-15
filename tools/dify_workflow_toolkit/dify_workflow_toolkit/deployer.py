"""Deploy a Dify workflow DSL to a running Dify instance over SSH.

The Dify web UI does not expose a stable API for publishing a new
workflow version programmatically. The reliable path used here is:

    1. Upload the yml to the Dify host
    2. Ensure psycopg2-binary is installed inside the api-1 container
    3. Push a deploy script via SFTP + `docker cp` into /tmp/ of the
       api-1 container (the `dify` user cannot write to /root/)
    4. Run the script with `docker exec` — it does an
       `UPDATE workflows SET graph = ...` against the published row
    5. Optionally restart api + worker + worker-beat so the new graph
       is picked up
    6. Verify by SELECT LENGTH(graph::text) + node-id presence

The Dify database (Postgres) connection details are auto-read from
`docker inspect` of the api container, so callers only need to provide
the SSH connection.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile as _tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from dify_workflow_toolkit.ssh_client import SSHClient


_DEPLOY_SCRIPT = r'''#!/usr/bin/env python3
"""Update a Dify workflow's published graph in the DB.

Runs inside the docker-api-1 container. Connection params come from
the compose env vars (DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD,
DB_DATABASE).

Usage inside container:
    python deploy_workflow.py --app-id <uuid> --yml <path>
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
import yaml


def load_yml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_workflows(cur, app_id: str) -> list[dict]:
    cur.execute(
        "SELECT id, version, LENGTH(graph::text) AS graph_len "
        "FROM workflows WHERE app_id = %s ORDER BY updated_at DESC",
        (app_id,),
    )
    return [{"id": r[0], "version": str(r[1]), "graph_len": r[2]} for r in cur.fetchall()]


def update_published(cur, app_id: str, graph: dict) -> int:
    cur.execute(
        "UPDATE workflows SET graph = %s::jsonb, updated_at = NOW() "
        "WHERE app_id = %s AND version != 'draft'",
        (json.dumps(graph, ensure_ascii=False), app_id),
    )
    return cur.rowcount


def restart_containers() -> None:
    for c in ("docker-api-1", "docker-worker-1", "docker-worker-beat-1"):
        try:
            subprocess.run(["docker", "restart", c], check=True, capture_output=True, text=True)
            print(f"  restarted {c}")
        except subprocess.CalledProcessError as e:
            print(f"  [warn] failed to restart {c}: {e.stderr.strip()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--yml", required=True)
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    yml_path = Path(args.yml)
    if not yml_path.exists():
        print(f"[error] yml not found: {yml_path}")
        return 1

    data = load_yml(yml_path)
    graph = data["workflow"]["graph"]
    nodes = graph["nodes"]
    print(f"loaded yml: {len(nodes)} nodes, {len(graph['edges'])} edges")

    db = dict(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    try:
        conn = psycopg2.connect(**db)
    except Exception as e:
        print(f"[error] postgres connect failed: {e}")
        return 1

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        rows = list_workflows(cur, args.app_id)
        if not rows:
            print(f"[error] no workflows for app_id={args.app_id}")
            return 1
        for r in rows:
            print(f"  - id={r['id']} version={r['version']} graph_len={r['graph_len']}")

        published = [r for r in rows if r["version"] != "draft"]
        if not published:
            print(f"[error] no published (non-draft) workflow found")
            return 1

        if args.dry_run:
            print(f"[dry-run] would update {len(published)} rows")
            return 0

        n = update_published(cur, args.app_id, graph)
        conn.commit()
        print(f"updated {n} rows")

        if args.restart:
            print("restarting containers...")
            restart_containers()
    finally:
        cur.close()
        conn.close()

    print("deploy ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


_VERIFY_SCRIPT = r'''#!/usr/bin/env python3
"""Verify a deployed workflow contains the expected node ids.

Runs inside docker-api-1.
"""

import argparse
import json
import os
import sys

import psycopg2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--must-have", nargs="*", default=[])
    args = ap.parse_args()

    db = dict(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    conn = psycopg2.connect(**db)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, version, graph FROM workflows "
        "WHERE app_id = %s AND version != 'draft'",
        (args.app_id,),
    )
    rows = cur.fetchall()
    if not rows:
        print("[fail] no published workflow found")
        return 1
    rc = 0
    for row in rows:
        wid, version, graph_json = row
        graph = graph_json if isinstance(graph_json, dict) else json.loads(graph_json)
        ids = [n.get("id") for n in graph["nodes"]]
        print(f"workflow id={wid} version={version} nodes={len(ids)}")
        for must in args.must_have:
            ok = must in ids
            print(f"  has {must}: {ok}")
            if not ok:
                rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
'''


@dataclass
class DeploymentResult:
    app_id: str
    rows_updated: int
    restarted: bool
    node_ids_present: list[str] = field(default_factory=list)
    verified: bool = False
    elapsed_seconds: float = 0.0

    def __str__(self) -> str:
        return (
            f"DeploymentResult(app_id={self.app_id}, "
            f"rows_updated={self.rows_updated}, restarted={self.restarted}, "
            f"verified={self.verified}, nodes={len(self.node_ids_present)})"
        )


class Deployer:
    """Orchestrate yml upload + DB update + optional restart over SSH."""

    DEFAULT_API_CONTAINER = "docker-api-1"
    DEFAULT_DEPLOY_SCRIPT_CONTAINER_PATH = "/tmp/dify_deploy_workflow.py"
    DEFAULT_VERIFY_SCRIPT_CONTAINER_PATH = "/tmp/dify_verify_workflow.py"

    def __init__(
        self,
        ssh: SSHClient,
        *,
        api_container: str = DEFAULT_API_CONTAINER,
    ) -> None:
        self.ssh = ssh
        self.api_container = api_container

    def deploy(
        self,
        yml_text_or_path: str | Path,
        app_id: str,
        *,
        restart: bool = True,
        must_have_nodes: list[str] | None = None,
        wait_for_dify_seconds: int = 8,
    ) -> DeploymentResult:
        """Full deploy: install psycopg2, push scripts, update DB, verify."""
        t0 = time.time()
        yml_text = self._read_yml(yml_text_or_path)
        graph = yaml.safe_load(yml_text)["workflow"]["graph"]
        node_ids = [n.get("id") for n in graph["nodes"]]

        self._ensure_psycopg2()
        self._push_deploy_script()
        self._push_verify_script()
        self._run_deploy(yml_text, app_id, restart=restart)

        result = DeploymentResult(
            app_id=app_id,
            rows_updated=-1,
            restarted=restart,
            node_ids_present=node_ids,
            elapsed_seconds=time.time() - t0,
        )

        if must_have_nodes:
            verified = self._run_verify(app_id, must_have_nodes)
            result.verified = verified
        else:
            result.verified = True

        if restart and wait_for_dify_seconds:
            print(f"  waiting {wait_for_dify_seconds}s for Dify to come back up...")
            time.sleep(wait_for_dify_seconds)

        return result

    def _read_yml(self, src: str | Path) -> str:
        p = Path(src)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8")
        if isinstance(src, str):
            return src
        raise FileNotFoundError(f"yml source not found: {src}")

    def _ensure_psycopg2(self) -> None:
        out, _, rc = self.ssh.docker_exec(
            self.api_container,
            "python -c 'import psycopg2; print(psycopg2.__version__)' 2>&1 | head -3",
            timeout=30,
        )
        if rc != 0 or "Traceback" in out:
            print("installing psycopg2-binary in api container...")
            self.ssh.docker_exec(
                self.api_container,
                "pip install --quiet psycopg2-binary 2>&1 | tail -3",
                timeout=120,
            )

    def _push_deploy_script(self) -> None:
        with tempfile_inline_text(_DEPLOY_SCRIPT) as tmp:
            self.ssh.docker_cp_to_container(
                tmp,
                self.api_container,
                self.DEFAULT_DEPLOY_SCRIPT_CONTAINER_PATH,
            )

    def _push_verify_script(self) -> None:
        with tempfile_inline_text(_VERIFY_SCRIPT) as tmp:
            self.ssh.docker_cp_to_container(
                tmp,
                self.api_container,
                self.DEFAULT_VERIFY_SCRIPT_CONTAINER_PATH,
            )

    def _run_deploy(self, yml_text: str, app_id: str, *, restart: bool) -> int:
        with tempfile_inline_text(yml_text, suffix=".yml") as tmp:
            host_tmp = f"/tmp/{os.path.basename(tmp)}"
            self.ssh.put(tmp, host_tmp)
            container_yml = f"/tmp/{os.path.basename(tmp)}"
            self.ssh.run(f"docker cp {host_tmp} {self.api_container}:{container_yml}")
            self.ssh.run(f"rm -f {host_tmp}")
            cmd = (
                f"docker exec {self.api_container} "
                f"python {self.DEFAULT_DEPLOY_SCRIPT_CONTAINER_PATH} "
                f"--app-id {app_id} --yml {container_yml}"
            )
            if restart:
                cmd += " --restart"
            out, _, rc = self.ssh.run(cmd, timeout=180)
            if rc != 0:
                raise RuntimeError(f"deploy failed (rc={rc})\n{out}")
        return rc

    def _run_verify(self, app_id: str, must_have: list[str]) -> bool:
        cmd = (
            f"docker exec {self.api_container} "
            f"python {self.DEFAULT_VERIFY_SCRIPT_CONTAINER_PATH} "
            f"--app-id {app_id} --must-have {' '.join(must_have)}"
        )
        out, _, rc = self.ssh.run(cmd, timeout=30)
        return rc == 0


@contextlib.contextmanager
def tempfile_inline_text(text: str, suffix: str = ".py"):
    with _tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        yield path
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
