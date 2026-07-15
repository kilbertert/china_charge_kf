"""Set the OSS bucket CORS rule that lets the H5 frontend load images.

This is intentionally a one-shot script (not part of the upload pipeline)
because the bucket-level CORS rule only needs to be applied once per
bucket-per-region. Re-running it is idempotent.

The CORS rule allows:

* Production H5 frontend: ``https://zcf.h5.qumall.qushiyun.com``
* Local Vite dev server: ``http://localhost:5173``

Methods: ``GET``, ``POST``, ``HEAD`` (POST is needed for the
``/api/chat`` FormData upload on the same bucket if it ever serves
presigned POSTs in the future). Headers: ``*`` so the browser can send
its own auth/Content-Type. Max age 3600s to spare the bucket from
preflight storms.

Prerequisite: the AK/SK in ``.oss-uploader/.env`` must have the
``oss:PutBucketCors`` permission (RAM policy
``AliyunOSSFullAccess`` or a custom policy with that action). If you see
``AccessDenied: The bucket you access does not belong to you``, ask the
bucket owner to attach the policy.

Run from the project root:
    python scripts/set_oss_cors.py
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys

import dotenv
import oss2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("set_oss_cors")

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".oss-uploader" / ".env"

H5_PROD_ORIGIN = "https://zcf.h5.qumall.qushiyun.com"
H5_LOCAL_ORIGIN = "http://localhost:5173"


def main() -> int:
    if not ENV_FILE.exists():
        log.error("Missing %s", ENV_FILE)
        return 2
    dotenv.load_dotenv(ENV_FILE)

    try:
        ak = os.environ["OSS_AK"]
        sk = os.environ["OSS_SK"]
        bucket_name = os.environ["OSS_BUCKET"]
        endpoint = os.environ["OSS_ENDPOINT"]
    except KeyError as e:
        log.error("Missing env var %s in %s", e, ENV_FILE)
        return 2

    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    rule = oss2.models.CorsRule(
        allowed_origins=[H5_PROD_ORIGIN, H5_LOCAL_ORIGIN],
        allowed_methods=["GET", "POST", "HEAD"],
        allowed_headers=["*"],
        expose_headers=["ETag", "Content-Length", "Content-Type"],
        max_age_seconds=3600,
    )
    cors = oss2.models.BucketCors(rules=[rule])
    bucket.put_bucket_cors(cors)
    log.info("CORS rule written to bucket: %s", bucket_name)

    # --- Read back to confirm ---
    got = bucket.get_bucket_cors()
    if not got.rules:
        log.error("Verification failed: no rules returned")
        return 1
    for i, r in enumerate(got.rules, 1):
        log.info("Rule %d:", i)
        log.info("  origins : %s", r.allowed_origins)
        log.info("  methods : %s", r.allowed_methods)
        log.info("  headers : %s", r.allowed_headers)
        log.info("  expose  : %s", r.expose_headers)
        log.info("  max_age : %s s", r.max_age_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
