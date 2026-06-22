"""Step 5: lee output de Bedrock Batch e inserta vectores en Aurora pgvector."""
import json
import os

import boto3

AURORA_SECRET_ARN = os.environ.get("AURORA_SECRET_ARN", "")
AURORA_CLUSTER_ARN = os.environ.get("AURORA_CLUSTER_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "")
SKIP_DB_INSERT = os.environ.get("SKIP_DB_INSERT", "false").lower() == "true"

s3 = boto3.client("s3")
rds = boto3.client("rds-data")


def list_output_files(bucket: str, prefix: str) -> list[str]:
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".jsonl.out"):
                keys.append(obj["Key"])
    return keys


def parse_record_id(record_id: str) -> tuple[str, int]:
    source_key, chunk_part = record_id.rsplit("::chunk_", 1)
    return source_key, int(chunk_part)


def bulk_upsert(rows: list[tuple]) -> int:
    sql = """
        UPDATE chunks
        SET embedding = :embedding::vector
        WHERE source_key = :source_key AND chunk_index = :chunk_index
    """
    updated = 0
    for i in range(0, len(rows), 1000):
        chunk = rows[i : i + 1000]
        parameter_sets = [
            [
                {"name": "embedding", "value": {"stringValue": json.dumps(emb)}},
                {"name": "source_key", "value": {"stringValue": src}},
                {"name": "chunk_index", "value": {"longValue": idx}},
            ]
            for src, idx, emb in chunk
        ]
        rds.batch_execute_statement(
            resourceArn=AURORA_CLUSTER_ARN,
            secretArn=AURORA_SECRET_ARN,
            database=DB_NAME,
            sql=sql,
            parameterSets=parameter_sets,
        )
        updated += len(chunk)
    return updated


def lambda_handler(event, context):
    bucket = event["bucket"]
    tenant = event["tenant"]
    run_id = event["run_id"]
    prefix = f"embeddings-output/{tenant}/{run_id}/"

    output_files = list_output_files(bucket, prefix)
    if not output_files:
        raise ValueError(f"No se encontraron archivos de output en {prefix}")

    rows = []
    for key in output_files:
        obj = s3.get_object(Bucket=bucket, Key=key)
        for line in obj["Body"].read().decode("utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            source_key, chunk_idx = parse_record_id(record["recordId"])
            embedding = record["modelOutput"]["embeddings"][0]
            rows.append((source_key, chunk_idx, embedding))

    total_updated = 0
    db_skipped = False
    if SKIP_DB_INSERT or not AURORA_CLUSTER_ARN:
        db_skipped = True
    else:
        total_updated = bulk_upsert(rows)

    summary = {
        "run_id": run_id,
        "tenant": tenant,
        "total_vectors_read": len(rows),
        "total_vectors_inserted": total_updated,
        "db_insert_skipped": db_skipped,
    }
    s3.put_object(
        Bucket=bucket,
        Key=f"pipeline-results/{run_id}/final_summary.json",
        Body=json.dumps(summary, indent=2).encode(),
    )

    return summary
