"""Step 3: consolida pending-embeddings en lotes de hasta 50K records para Bedrock Batch."""
import json
import os

import boto3

MAX_RECORDS_PER_JOB = 50_000
s3 = boto3.client("s3")


def list_pending_jsonl(bucket: str, tenant: str, run_id: str) -> list[str]:
    prefix = f"pending-embeddings/{tenant}/{run_id}/"
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def lambda_handler(event, context):
    bucket = event["bucket"]
    tenant = event["tenant"]
    run_id = event["run_id"]

    pending_keys = list_pending_jsonl(bucket, tenant, run_id)
    if not pending_keys:
        raise ValueError(f"No hay archivos pending-embeddings para run_id={run_id}")

    all_records = []
    for key in pending_keys:
        obj = s3.get_object(Bucket=bucket, Key=key)
        for line in obj["Body"].read().decode("utf-8").splitlines():
            if line.strip():
                all_records.append(line)

    batch_input_keys = []
    for i in range(0, len(all_records), MAX_RECORDS_PER_JOB):
        batch_records = all_records[i : i + MAX_RECORDS_PER_JOB]
        idx = i // MAX_RECORDS_PER_JOB + 1
        batch_key = f"embeddings-input/{tenant}/{run_id}/batch_{idx}.jsonl"
        s3.put_object(
            Bucket=bucket,
            Key=batch_key,
            Body="\n".join(batch_records).encode("utf-8"),
        )
        batch_input_keys.append(batch_key)

    return {
        "run_id": run_id,
        "tenant": tenant,
        "bucket": bucket,
        "total_chunks": len(all_records),
        "batch_input_keys": batch_input_keys,
    }
