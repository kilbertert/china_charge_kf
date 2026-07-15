#!/usr/bin/env python3
"""Auto-deploy scene_classifier_v2 to Dify via SSH + psycopg2 in api container."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko
import yaml

# ── config ──────────────────────────────────────────────────────
SSH_HOST = "124.243.178.156"
SSH_PORT = 22
SSH_USER = "root"
SSH_PASS = "Xbjiejiaqsy@2026"

LOCAL_YML = Path(__file__).resolve().parents[1] / "Workflow-China_charge_seriver-draft-9380" / "workflow" / "AI_health_consultant_v2.yml"
REMOTE_YML = "/root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/AI_health_consultant_v2.yml"
REMOTE_DEPLOY_SCRIPT = "/root/dify/china_charge_kf/scripts/deploy_v2_scene_classifier.py"
DEFAULT_APP_ID = "d2623d9a-ac8e-40b6-9ba8-ded2f99f874a"


class SSHClient:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS, timeout=30)
        print(f"  connected to {SSH_USER}@{SSH_HOST}:{SSH_PORT}")

    def run(self, cmd: str, timeout: int = 60) -> tuple:
        print(f"\n>>> {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(f"[stderr] {err.rstrip()}")
        print(f"[exit={rc}]")
        return out, err, rc

    def put(self, local: Path, remote: str) -> None:
        print(f"\n>>> put {local.name} -> {remote}")
        sftp = self.client.open_sftp()
        sftp.put(str(local), remote)
        sftp.close()

    def close(self):
        self.client.close()


def step_upload_yml(ssh: SSHClient) -> None:
    print("\n" + "=" * 70)
    print("STEP 1: Upload updated yml to server")
    print("=" * 70)
    if not LOCAL_YML.exists():
        raise FileNotFoundError(f"Local yml not found: {LOCAL_YML}")
    data = yaml.safe_load(LOCAL_YML.read_text(encoding="utf-8"))
    nodes = data["workflow"]["graph"]["nodes"]
    has_4080 = any(n.get("id") == "4080" for n in nodes)
    has_4002 = any(n.get("id") == "4002" for n in nodes)
    if not (has_4080 and has_4002):
        raise RuntimeError(f"yml missing required nodes: 4080={has_4080} 4002={has_4002}")
    print(f"  local yml OK: {len(nodes)} nodes, has 4080={has_4080} 4002={has_4002}")
    ssh.run(f"mkdir -p '{Path(REMOTE_YML).parent}'")
    ssh.put(LOCAL_YML, REMOTE_YML)
    ssh.run(f"ls -la '{REMOTE_YML}' && wc -l '{REMOTE_YML}'")


def step_check_docker(ssh: SSHClient) -> None:
    print("\n" + "=" * 70)
    print("STEP 2: Check Dify containers running")
    print("=" * 70)
    ssh.run("docker ps --format 'table {{.Names}}\\t{{.Status}}' | grep -E 'docker-(api|worker|db|nginx)-1' || echo 'no containers matched'")


def step_deploy(ssh: SSHClient) -> None:
    print("\n" + "=" * 70)
    print("STEP 3: Update published workflow graph in Dify DB")
    print("=" * 70)

    # Check if psycopg2 in api container
    out, _, rc = ssh.run("docker exec docker-api-1 python -c 'import psycopg2; print(psycopg2.__version__)' 2>&1 | head -3")
    if rc != 0:
        print("  installing psycopg2-binary...")
        ssh.run("docker exec docker-api-1 pip install --quiet psycopg2-binary 2>&1 | tail -3")

    # Upload deploy script if not present
    ssh.run(f"docker exec docker-api-1 bash -c 'mkdir -p /root/dify/china_charge_kf/scripts'")
    local_script = Path(__file__).resolve().parent / "deploy_v2_scene_classifier.py"
    ssh.put(local_script, "/tmp/deploy_v2_scene_classifier.py")
    ssh.run("docker cp /tmp/deploy_v2_scene_classifier.py docker-api-1:/root/dify/china_charge_kf/scripts/deploy_v2_scene_classifier.py")

    # Run it with restart
    ssh.run(
        f"docker exec docker-api-1 python /root/dify/china_charge_kf/scripts/deploy_v2_scene_classifier.py "
        f"--app-id {DEFAULT_APP_ID} --restart 2>&1",
        timeout=180,
    )


def step_verify(ssh: SSHClient) -> None:
    print("\n" + "=" * 70)
    print("STEP 4: Verify published graph has 4080")
    print("=" * 70)
    # Use the host's psql if available, or docker exec
    check_cmd = (
        f"docker exec docker-api-1 python -c \""
        f"import json, psycopg2, os\\n"
        f"conn = psycopg2.connect(host=os.environ.get('DB_HOST','db'), port=int(os.environ.get('DB_PORT','5432')), "
        f"user=os.environ.get('DB_USERNAME','postgres'), "
        f"password=os.environ.get('DB_PASSWORD','postgres'), "
        f"dbname=os.environ.get('DB_DATABASE','dify'))\\n"
        f"cur = conn.cursor()\\n"
        f"cur.execute(\\\"SELECT id, version, LENGTH(graph::text) FROM workflows WHERE app_id='{DEFAULT_APP_ID}' AND version != 'draft'\\\")\\n"
        f"for r in cur.fetchall(): print('  id=%s version=%s graph_len=%s' % r)\\n"
        f"cur.execute(\\\"SELECT graph FROM workflows WHERE app_id='{DEFAULT_APP_ID}' AND version != 'draft' LIMIT 1\\\")\\n"
        f"g = cur.fetchone()[0]\\n"
        f"d = json.loads(g)\\n"
        f"ids = [n.get('id') for n in d['nodes']]\\n"
        f"print('  total nodes: %d' % len(d['nodes']))\\n"
        f"print('  has 4080: %s' % ('4080' in ids))\\n"
        f"print('  has 4002: %s' % ('4002' in ids))\\n"
        f"print('  has 4003: %s' % ('4003' in ids))\\n"
        f"\\\"\""
    )
    ssh.run(check_cmd, timeout=30)


def step_test(ssh: SSHClient) -> None:
    print("\n" + "=" * 70)
    print("STEP 5: Test workflow via /api/health-consult/chat")
    print("=" * 70)
    test_cases = [
        ("leg_pain", "我右小腿胀痛 腰间盘突出 压迫神经", "symptom"),
        ("bone_density", "我56岁,女性,已绝经,腰椎L1-L4 T值-2.1,骨量减少", "report"),
        ("product", "补钙产品哪个好", "product"),
        ("greeting", "你好", "symptom"),
        ("negation", "我腿不疼,没有不舒服", "symptom"),
        ("knee", "我膝盖疼是怎么回事", "symptom"),
    ]

    # Wait for Dify to be ready (api + worker restart)
    print("  waiting 10s for Dify services to come back up...")
    import time
    time.sleep(10)

    # Check health
    out, _, _ = ssh.run("curl -s -m 5 http://127.0.0.1:8013/api/health-consult/health 2>&1 | head -3")
    if "ok" not in out.lower() and "{" not in out:
        print("  [warn] backend not responding, trying api:5001 directly...")
        ssh.run("curl -s -m 5 http://api:5001/v1/workflows/run 2>&1 | head -3 || true")

    for case_id, text, expected_scene in test_cases:
        cmd = (
            f"curl -s -m 60 -X POST 'http://127.0.0.1:8013/api/health-consult/chat' "
            f"-F 'text={text}' -F 'session_id=v2-test-{case_id}' 2>&1 | head -c 3000"
        )
        out, _, _ = ssh.run(cmd, timeout=90)
        # Try parse
        scene = "?"
        try:
            # find JSON in output
            start = out.find("{")
            end = out.rfind("}")
            if start >= 0 and end > start:
                resp = json.loads(out[start : end + 1])
                scene = resp.get("scene", "?")
        except Exception:
            pass
        ok = "✓" if scene == expected_scene else "✗"
        print(f"  {ok} {case_id}: scene={scene} (expected={expected_scene})")


def main() -> int:
    print(f"Connecting to {SSH_USER}@{SSH_HOST}:{SSH_PORT}...")
    ssh = SSHClient()
    try:
        step_upload_yml(ssh)
        step_check_docker(ssh)
        step_deploy(ssh)
        step_verify(ssh)
        step_test(ssh)
    finally:
        ssh.close()
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
