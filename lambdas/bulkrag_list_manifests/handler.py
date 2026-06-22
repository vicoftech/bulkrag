"""Step 1: lista PDFs, genera run_id, particiona en manifests."""
import json
import os
import uuid
from datetime import datetime

import boto3

BUCKET = os.environ["RAG_BUCKET_NAME"]
s3 = boto3.client("s3")


def list_pdf_keys(bucket: str, prefix: str, max_files: int | None = None) -> list[str]:
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".pdf"):
                keys.append(obj["Key"])
                if max_files and len(keys) >= max_files:
                    return keys
    return keys


def lambda_handler(event, context):
    tenant = event["tenant"]
    prefix = event["prefix"]
    per_manifest = event.get("files_per_manifest", 200)
    max_files = event.get("max_files")

    run_id = f"{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"

    all_keys = list_pdf_keys(BUCKET, prefix, max_files=max_files)
    if not all_keys:
        raise ValueError(f"No se encontraron PDFs en s3://{BUCKET}/{prefix}")

    manifest_keys = []
    for i in range(0, len(all_keys), per_manifest):
        batch = all_keys[i : i + per_manifest]
        idx = i // per_manifest + 1
        manifest_key = f"batch-poc/manifests/{tenant}/{run_id}/tanda_{idx}.json"
        s3.put_object(
            Bucket=BUCKET,
            Key=manifest_key,
            Body=json.dumps({"batch": idx, "total": len(batch), "keys": batch}).encode(),
        )
        manifest_keys.append(manifest_key)

    return {
        "run_id": run_id,
        "tenant": tenant,
        "bucket": BUCKET,
        "total_files": len(all_keys),
        "manifest_keys": manifest_keys,
    }
