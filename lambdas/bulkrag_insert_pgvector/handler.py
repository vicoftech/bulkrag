"""Step 5: lee output de Bedrock e inserta vectores en Aurora pgvector vía psycopg2."""
import json
import os

import boto3
import psycopg2
from psycopg2.extras import execute_batch

AURORA_SECRET_ARN = os.environ.get("AURORA_SECRET_ARN", "")
SKIP_DB_INSERT = os.environ.get("SKIP_DB_INSERT", "false").lower() == "true"
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))

s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager")

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    tenant TEXT NOT NULL,
    source_key TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector({EMBEDDING_DIM}),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_key, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_tenant ON chunks (tenant);
"""


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


def extract_embedding(model_output: dict) -> list:
    if "embedding" in model_output:
        return model_output["embedding"]
    if "embeddings" in model_output:
        embeddings = model_output["embeddings"]
        return embeddings[0] if embeddings else []
    raise ValueError(f"Formato de embedding no reconocido: {list(model_output)}")


def get_connection():
    secret = json.loads(
        secrets.get_secret_value(SecretId=AURORA_SECRET_ARN)["SecretString"]
    )
    return psycopg2.connect(
        host=secret["host"],
        port=int(secret.get("port", 5432)),
        user=secret["username"],
        password=secret["password"],
        dbname=secret["dbname"],
        connect_timeout=15,
    )


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()


def bulk_upsert(tenant: str, rows: list[tuple]) -> int:
    sql = """
        INSERT INTO chunks (tenant, source_key, chunk_index, embedding, updated_at)
        VALUES (%s, %s, %s, %s::vector, NOW())
        ON CONFLICT (source_key, chunk_index) DO UPDATE
        SET embedding = EXCLUDED.embedding,
            tenant = EXCLUDED.tenant,
            updated_at = NOW()
    """
    params = [
        (tenant, src, idx, json.dumps(emb)) for src, idx, emb in rows
    ]

    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            execute_batch(cur, sql, params, page_size=500)
        conn.commit()

    return len(params)


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
            embedding = extract_embedding(record["modelOutput"])
            rows.append((source_key, chunk_idx, embedding))

    total_updated = 0
    db_skipped = False
    if SKIP_DB_INSERT or not AURORA_SECRET_ARN:
        db_skipped = True
    else:
        total_updated = bulk_upsert(tenant, rows)

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
