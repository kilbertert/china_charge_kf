"""Deploy frontend dist/ to the china-charge-frontend container.

Replaces ALL old assets in /usr/share/nginx/html/assets/ with new ones,
and replaces /usr/share/nginx/html/index.html with the new one.
Reloads nginx afterwards.

Usage: python tools/deploy_frontend.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import paramiko

HOST = "124.243.178.156"
USER = "root"
PASS = "Xbjiejiaqsy@2026"

FRONTEND_CONTAINER = "china-charge-frontend"
LOCAL_DIST = Path(r"D:/AI/company-projects/ai-customer/china_charge_kf/frontend/dist")


def sftp_put_dir(sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str) -> int:
    """Recursively upload a local dir to a remote dir via SFTP."""
    count = 0
    for p in local_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(local_dir).as_posix()
        remote_path = f"{remote_dir}/{rel}"
        sftp.put(str(p), remote_path)
        count += 1
    return count


def main() -> int:
    if not LOCAL_DIST.exists():
        print(f"ERROR: {LOCAL_DIST} does not exist. Run `npm run build` first.")
        return 1

    # Build the tar in a known location (Windows temp can have path quirks)
    bundle = Path(r"D:/AI/company-projects/ai-customer/china_charge_kf/.fe_deploy_bundle.tar")
    if bundle.exists():
        bundle.unlink()
    print(f"Packaging {LOCAL_DIST} into {bundle} ...")
    shutil.make_archive(str(bundle.with_suffix("")), "tar", root_dir=str(LOCAL_DIST.parent), base_dir=LOCAL_DIST.name)
    if not bundle.exists():
        print(f"ERROR: bundle not found at {bundle}")
        # Try alternate path
        alt = Path(r"C:/Users/q1234/AppData/Local/Temp/fe_deploy_bundle.tar")
        print(f"Trying alternate path: {alt}")
        shutil.make_archive(str(alt.with_suffix("")), "tar", root_dir=str(LOCAL_DIST.parent), base_dir=LOCAL_DIST.name)
        if alt.exists():
            bundle = alt
        else:
            return 1
    print(f"bundle size: {bundle.stat().st_size} bytes")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASS, timeout=30)
    print(f"connected to {USER}@{HOST}")

    sftp = c.open_sftp()
    sftp.put(str(bundle), "/tmp/fe_dist.tar")
    print(f"uploaded {bundle.name} -> /tmp/fe_dist.tar")
    sftp.close()

    cmds = [
        # Extract into a clean staging dir on host
        "mkdir -p /tmp/fe_stage && rm -rf /tmp/fe_stage/* && tar -xf /tmp/fe_dist.tar -C /tmp/fe_stage",
        # Sanity check (the tar has a 'dist/' top dir from shutil.make_archive base_dir)
        "ls -la /tmp/fe_stage/ && echo --- dist --- && ls -la /tmp/fe_stage/dist/ && echo --- assets --- && ls -la /tmp/fe_stage/dist/assets/",
    ]
    for cmd in cmds:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print("STDERR:", err)

    # Wipe old assets and copy in new ones via docker cp
    cmds2 = [
        # Use a single docker exec + sh -c so we can run multi-line commands inside the container
        f'docker exec {FRONTEND_CONTAINER} sh -c "rm -rf /usr/share/nginx/html/assets && mkdir -p /usr/share/nginx/html/assets"',
    ]
    for cmd in cmds2:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print("STDERR:", err)

    # Copy assets and index.html (note: stage dir is /tmp/fe_stage/dist, not /tmp/fe_stage/)
    cmds3 = [
        f"docker cp /tmp/fe_stage/dist/index.html {FRONTEND_CONTAINER}:/usr/share/nginx/html/index.html",
        f"docker cp /tmp/fe_stage/dist/vite.svg {FRONTEND_CONTAINER}:/usr/share/nginx/html/vite.svg",
        f"docker cp /tmp/fe_stage/dist/assets/. {FRONTEND_CONTAINER}:/usr/share/nginx/html/assets/",
    ]
    for cmd in cmds3:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print("STDERR:", err)

    # Verify the new files are in place
    cmds4 = [
        f"docker exec {FRONTEND_CONTAINER} ls -la /usr/share/nginx/html/",
        f"docker exec {FRONTEND_CONTAINER} ls -la /usr/share/nginx/html/assets/",
        f"docker exec {FRONTEND_CONTAINER} cat /usr/share/nginx/html/index.html",
    ]
    for cmd in cmds4:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print("STDERR:", err)

    # Reload nginx
    cmd_reload = f"docker exec {FRONTEND_CONTAINER} nginx -s reload"
    print(f"\n>>> {cmd_reload}")
    stdin, stdout, stderr = c.exec_command(cmd_reload, timeout=30)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("STDERR:", err)

    # Cleanup host tmp
    c.exec_command("rm -rf /tmp/fe_stage /tmp/fe_dist.tar", timeout=10)

    c.close()
    print("\n=== deploy done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
