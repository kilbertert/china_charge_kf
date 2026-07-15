"""Dify KB 批量上传器。

绕过控制台 5 文件限制,通过 console API 上传整个 MD 目录到指定 KB。
流程:
  1. POST /files/upload (multipart) → file_id
  2. POST /datasets/<id>/documents (JSON) → document
"""
from __future__ import annotations
import os
import json
import base64
import http.cookiejar
import urllib.request
import urllib.error
import time
from pathlib import Path


def _login(api_base: str, email: str = "2634141585@qq.com", password: str = "admin123"):
    """登录 Dify 控制台,返回 opener + csrf。"""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    b64 = base64.b64encode(password.encode()).decode()
    req = urllib.request.Request(
        f"{api_base}/console/api/login",
        data=json.dumps({"email": email, "password": b64}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener.open(req, timeout=10).read()
    csrf = next((c.value for c in cj if c.name == "csrf_token"), None)
    return opener, csrf


def _upload_file(opener, csrf: str, api_base: str, filepath: str, max_retries: int = 3) -> str | None:
    """上传单个文件到 Dify,返回 file_id。"""
    boundary = "----formdata" + os.urandom(8).hex()
    content = open(filepath, "rb").read()
    fn = os.path.basename(filepath)
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="source"\r\n\r\ndatasets\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fn}"\r\nContent-Type: text/markdown\r\n\r\n'
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{api_base}/console/api/files/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-CSRF-Token": csrf},
        method="POST",
    )
    for attempt in range(max_retries):
        try:
            with opener.open(req, timeout=60) as r:
                d = json.loads(r.read())
                return d.get("id")
        except urllib.error.HTTPError as e:
            if attempt == max_retries - 1:
                print(f"  upload err: {e.code} {e.read().decode()[:200]}")
                return None
            time.sleep(1)


def _create_document(opener, csrf: str, api_base: str, kb_id: str, file_id: str, max_retries: int = 3) -> str | None:
    """创建文档,返回 doc_id。"""
    payload = {
        "indexing_technique": "high_quality",
        "process_rule": {"mode": "automatic"},
        "doc_form": "text_model",
        "doc_language": "Chinese",
        "data_source": {"info_list": {"data_source_type": "upload_file", "file_info_list": {"file_ids": [file_id]}}},
    }
    req = urllib.request.Request(
        f"{api_base}/console/api/datasets/{kb_id}/documents",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
        method="POST",
    )
    for attempt in range(max_retries):
        try:
            with opener.open(req, timeout=60) as r:
                d = json.loads(r.read())
                docs = d.get("documents", [])
                return docs[0].get("id") if docs else None
        except urllib.error.HTTPError as e:
            if attempt == max_retries - 1:
                print(f"  create err: {e.code} {e.read().decode()[:200]}")
                return None
            time.sleep(1)


def bulk_upload(kb_id: str, md_dir: str, api_key: str = "",
                api_base: str = "http://127.0.0.1:8501",
                email: str = "2634141585@qq.com", password: str = "admin123",
                sleep: float = 0.15) -> dict:
    """批量上传 MD 目录到 Dify KB。

    Returns:
        {"uploaded": int, "errors": int, "files": list[str]}
    """
    md_path = Path(md_dir)
    files = sorted(md_path.glob("*.md"))
    print(f"准备上传 {len(files)} 个文件到 KB {kb_id[:8]}...")

    opener, csrf = _login(api_base, email, password)
    if not csrf:
        return {"uploaded": 0, "errors": len(files), "files": []}

    uploaded = 0
    errors = 0
    failed_files = []

    for i, fp in enumerate(files, 1):
        file_id = _upload_file(opener, csrf, api_base, str(fp))
        if not file_id:
            errors += 1
            failed_files.append(str(fp))
            continue
        doc_id = _create_document(opener, csrf, api_base, kb_id, file_id)
        if not doc_id:
            errors += 1
            failed_files.append(str(fp))
            continue
        uploaded += 1
        if i % 20 == 0:
            print(f"  Progress {i}/{len(files)} (ok={uploaded}, err={errors})")
        time.sleep(sleep)

    return {
        "uploaded": uploaded,
        "errors": errors,
        "files": failed_files,
    }