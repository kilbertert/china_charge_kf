"""Thin paramiko wrapper for one-off SSH command + SFTP operations.

The Dify deployer uses this to:
  1. Run `docker exec ...` to run scripts inside the api container
  2. Use SFTP to push a deploy script to the host, then `docker cp`
     to copy it into the container (handles /root permission issues
     that come from Dify running as user `dify`)

Why not use sshpass / expect?  paramiko handles password auth natively
and gives us back proper Python objects — no shell-escaping nightmares.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import paramiko


class SSHClient:
    """A short-lived paramiko client with sane defaults for Dify hosts."""

    def __init__(
        self,
        host: str,
        *,
        user: str = "root",
        password: str | None = None,
        port: int = 22,
        key_filename: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.host = host
        self.user = user
        self.port = port
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict[str, Any] = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }
        if password:
            kwargs["password"] = password
        if key_filename:
            kwargs["key_filename"] = key_filename
        self.client.connect(**kwargs)

    def close(self) -> None:
        if self.client:
            self.client.close()

    def __enter__(self) -> "SSHClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def run(self, cmd: str, *, timeout: int = 60, check: bool = False) -> tuple[str, str, int]:
        """Execute a command. Returns (stdout, stderr, exit_code)."""
        preview = cmd if len(cmd) <= 200 else cmd[:200] + "..."
        print(f">>> {preview}")
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(f"[stderr] {err.rstrip()}")
        print(f"[exit={rc}]")
        if check and rc != 0:
            raise RuntimeError(f"command failed (rc={rc}): {preview}\nstderr: {err}")
        return out, err, rc

    def put(self, local: str | Path, remote: str) -> None:
        local = Path(local)
        if not local.exists():
            raise FileNotFoundError(f"local file not found: {local}")
        sftp = self.client.open_sftp()
        try:
            sftp.put(str(local), remote)
        finally:
            sftp.close()
        print(f"put {local.name} -> {remote}")

    def put_text(self, text: str, remote: str) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(text)
            tmp_path = f.name
        try:
            self.put(tmp_path, remote)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def docker_exec(self, container: str, cmd: str, *, timeout: int = 60) -> tuple[str, str, int]:
        return self.run(f"docker exec {container} {cmd}", timeout=timeout)

    def docker_cp_to_container(self, local: str | Path, container: str, container_path: str) -> None:
        local = Path(local)
        host_tmp = f"/tmp/{uuid.uuid4().hex}_{local.name}"
        self.put(local, host_tmp)
        try:
            self.run(f"docker cp {host_tmp} {container}:{container_path}")
        finally:
            self.run(f"rm -f {host_tmp}")
