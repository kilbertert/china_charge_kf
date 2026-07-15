"""Inline yml deploy: upload to server, run psycopg2 update in api-1 container.

Use this when the legacy `scripts/ssh_deploy.py` or the toolkit's deployer
fail (permission issues on /root, SQL escaping, etc.). Writes to /tmp only.
"""

from __future__ import annotations

from pathlib import Path

import paramiko

HOST = "124.243.178.156"
USER = "root"
PASS = "Xbjiejiaqsy@2026"
APP_ID = "d2623d9a-ac8e-40b6-9ba8-ded2f99f874a"
LOCAL_YML = Path(r"D:/AI/company-projects/ai-customer/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/AI_health_consultant_v2.yml")
REMOTE_YML = "/tmp/AI_health_consultant_v2.yml"

DEPLOY_PY = r'''
import json, os, sys, yaml
import psycopg2

YML = "/tmp/AI_health_consultant_v2.yml"
APP_ID = "d2623d9a-ac8e-40b6-9ba8-ded2f99f874a"

data = yaml.safe_load(open(YML, encoding="utf-8"))
new_graph = data["workflow"]["graph"]

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    user=os.environ["DB_USERNAME"],
    password=os.environ["DB_PASSWORD"],
    dbname=os.environ["DB_DATABASE"],
)
cur = conn.cursor()

cur.execute(
    "SELECT id, version, LENGTH(graph::text) FROM workflows WHERE app_id=%s AND version != 'draft' ORDER BY updated_at DESC",
    (APP_ID,),
)
rows = cur.fetchall()
print(f"BEFORE: published workflow(s)={len(rows)} for app_id={APP_ID}")
for r in rows:
    print(f"  id={str(r[0])[:8]} version={r[1]} graph_len={r[2]}")

if rows:
    graph_json = json.dumps(new_graph, ensure_ascii=False)
    cur.execute(
        "UPDATE workflows SET graph = %s::jsonb, updated_at = NOW() WHERE app_id=%s AND version != 'draft'",
        (graph_json, APP_ID),
    )
    print(f"UPDATED rowcount={cur.rowcount}")
    conn.commit()
else:
    print("NO PUBLISHED ROW FOUND - need to publish in Dify UI first")

cur.execute(
    "SELECT id, version, LENGTH(graph::text) FROM workflows WHERE app_id=%s AND version != 'draft' ORDER BY updated_at DESC",
    (APP_ID,),
)
print("AFTER:")
for r in cur.fetchall():
    print(f"  id={str(r[0])[:8]} version={r[1]} graph_len={r[2]}")
cur.close()
conn.close()
'''


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASS, timeout=30)
    print(f"connected to {USER}@{HOST}")

    sftp = c.open_sftp()
    sftp.put(str(LOCAL_YML), REMOTE_YML)
    print(f"uploaded {LOCAL_YML.name} -> {REMOTE_YML}")

    with sftp.open("/tmp/inline_deploy.py", "w") as f:
        f.write(DEPLOY_PY)
    sftp.close()
    print("wrote /tmp/inline_deploy.py")

    cmd = (
        f"docker cp {REMOTE_YML} docker-api-1:{REMOTE_YML} && "
        f"docker cp /tmp/inline_deploy.py docker-api-1:/tmp/inline_deploy.py && "
        f"docker exec docker-api-1 python /tmp/inline_deploy.py"
    )
    print(f"\nrunning: {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=180)
    print("\n--- STDOUT ---")
    print(stdout.read().decode())
    print("--- STDERR ---")
    print(stderr.read().decode())
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
