"""Batch-upload charge-pile KB images from kb-assets/images/ to Aliyun OSS.

Reads kb-assets/MANIFEST.md, skips rows whose Notes column contains
``sample-only-no-publish`` (currently only the QR-code image), and uploads the
remainder concurrently. After upload it rewrites the manifest with an added
``OSS URL`` column.

Idempotent: a re-run on a manifest that already has ``OSS URL`` filled in
will only upload rows that are still missing it. The parser also handles the
pre-rewrite 6-column form, so a fresh manifest works on the very first run.

Usage (from project root):
    python scripts/upload_kb_images.py
    python scripts/upload_kb_images.py --dry-run     # parse only, no upload
    python scripts/upload_kb_images.py --workers 16  # tune concurrency
"""

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import dotenv
import oss2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("upload_kb_images")

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "kb-assets" / "MANIFEST.md"
IMAGES_DIR = PROJECT_ROOT / "kb-assets" / "images"
ENV_FILE = PROJECT_ROOT / ".oss-uploader" / ".env"


def _parse_row(line: str) -> dict | None:
    """Parse one table row. Returns None for header/separator/non-data rows.

    Supports both 6-column (pre-rewrite) and 7-column (post-rewrite) forms.
    """
    s = line.strip()
    if not s.startswith("|"):
        return None
    cells = [c.strip() for c in s.strip("|").split("|")]
    if len(cells) not in (6, 7) or not cells[0].isdigit():
        return None
    if len(cells) == 6:
        num, filename, context, desc, oss_key, notes = cells
        oss_url = ""
    else:  # 7 columns
        num, filename, context, desc, oss_key, oss_url, notes = cells
    return {
        "num": int(num),
        "filename": filename.strip("`").strip(),
        "context": context,
        "description": desc,
        "oss_key": oss_key,
        "oss_url": oss_url,
        "notes": notes,
    }


def parse_manifest(text: str) -> list[dict]:
    """Parse the markdown table into list of dicts (one per data row)."""
    rows: list[dict] = []
    for line in text.splitlines():
        r = _parse_row(line)
        if r is not None:
            rows.append(r)
    return rows


def rewrite_manifest_table(original: str, rows: Iterable[dict]) -> str:
    """Rewrite the manifest table block with an added ``OSS URL`` column.

    Preserves any text before/after the table. Output header is:
    ``| # | Filename | Context heading | Description | OSS key | OSS URL | Notes |``
    """
    lines = original.splitlines()

    table_start: int | None = None
    table_end: int = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|"):
            if table_start is None:
                table_start = i
            table_end = i + 1
        elif table_start is not None:
            break

    if table_start is None:
        raise ValueError("Could not find a manifest table to rewrite")

    new_table: list[str] = [
        "| # | Filename | Context heading | Description | OSS key | OSS URL | Notes |",
        "|---|----------|-----------------|-------------|---------|---------|-------|",
    ]
    for r in sorted(rows, key=lambda x: x["num"]):
        url = r.get("oss_url", "") or ""
        new_table.append(
            f"| {r['num']} | `{r['filename']}` | {r['context']} | "
            f"{r['description']} | {r['oss_key']} | {url} | {r['notes']} |"
        )

    before = lines[:table_start]
    after = lines[table_end:]
    return "\n".join(before + new_table + after) + "\n"


def upload_one(
    bucket: oss2.Bucket, public_base: str, prefix: str, row: dict
) -> tuple[dict, str | None]:
    """Upload one image. Mutates ``row`` in place on success."""
    obj_key = f"{prefix.rstrip('/')}/{row['filename']}"
    local = IMAGES_DIR / row["filename"]
    if not local.exists():
        return row, f"local file missing: {local}"
    try:
        bucket.put_object_from_file(
            obj_key,
            str(local),
            headers={
                "Content-Type": "image/png",
                "Cache-Control": "public, max-age=31536000",
            },
        )
    except oss2.exceptions.OssError as e:
        return row, f"oss error: {e}"
    row["oss_key"] = obj_key
    row["oss_url"] = f"{public_base.rstrip('/')}/{obj_key}"
    return row, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not ENV_FILE.exists():
        log.error("Missing %s - copy your OSS credentials there first", ENV_FILE)
        return 2

    dotenv.load_dotenv(ENV_FILE)
    try:
        ak = os.environ["OSS_AK"]
        sk = os.environ["OSS_SK"]
        bucket_name = os.environ["OSS_BUCKET"]
        endpoint = os.environ["OSS_ENDPOINT"]
        public_base = os.environ["OSS_PUBLIC_BASE"]
        prefix = os.environ["OSS_KEY_PREFIX"]
    except KeyError as e:
        log.error("Missing env var %s in %s", e, ENV_FILE)
        return 2

    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    original_text = MANIFEST_PATH.read_text(encoding="utf-8")
    rows = parse_manifest(original_text)
    log.info("Parsed %d manifest rows from %s", len(rows), MANIFEST_PATH.name)
    if not rows:
        log.error("No rows parsed - manifest format may have changed")
        return 2

    # --- Categorize rows ---
    to_skip: list[dict] = []
    already_uploaded: list[dict] = []
    to_upload: list[dict] = []
    for r in rows:
        if "sample-only-no-publish" in r["notes"].lower():
            to_skip.append(r)
            continue
        if r.get("oss_url"):
            already_uploaded.append(r)
            continue
        to_upload.append(r)

    log.info(
        "skip=%d (sample-only) | already=%d | to_upload=%d",
        len(to_skip),
        len(already_uploaded),
        len(to_upload),
    )

    if args.dry_run:
        for r in to_upload:
            log.info("would upload: row=%d %s", r["num"], r["filename"])
        return 0

    # --- Upload concurrently ---
    lock = threading.Lock()
    success = 0
    failed: list[tuple[dict, str]] = []

    def _worker(r: dict) -> tuple[dict, str | None]:
        return upload_one(bucket, public_base, prefix, r)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_worker, r): r for r in to_upload}
        for fut in as_completed(futures):
            row, err = fut.result()
            with lock:
                if err:
                    failed.append((row, err))
                    log.warning("FAIL row=%d %s: %s", row["num"], row["filename"], err)
                else:
                    success += 1
                    log.info("OK   row=%d -> %s", row["num"], row["oss_url"])

    # --- Rewrite manifest with the new OSS URL column ---
    new_text = rewrite_manifest_table(original_text, rows)
    MANIFEST_PATH.write_text(new_text, encoding="utf-8")
    log.info("Manifest rewritten: %s", MANIFEST_PATH)

    # --- Summary ---
    log.info("=" * 56)
    log.info("Upload summary")
    log.info("  Total records    : %d", len(rows))
    log.info("  Skipped (QR etc.): %d", len(to_skip))
    log.info("  Already uploaded : %d", len(already_uploaded))
    log.info("  Newly uploaded   : %d", success)
    log.info("  Failed           : %d", len(failed))
    log.info("=" * 56)
    if failed:
        for r, err in failed:
            log.error("  - row %d (%s): %s", r["num"], r["filename"], err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
