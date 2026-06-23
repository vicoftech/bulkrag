"""Step 6: genera reporte HTML del run del pipeline bulkrag."""
import html
import json
import os
from datetime import datetime, timezone

import boto3

BUCKET = os.environ["RAG_BUCKET_NAME"]
FARGATE_VCPU = float(os.environ.get("FARGATE_VCPU", "4"))
FARGATE_MEMORY_GB = float(os.environ.get("FARGATE_MEMORY_GB", "8"))
FARGATE_VCPU_HOUR_USD = float(os.environ.get("FARGATE_VCPU_HOUR_USD", "0.04048"))
FARGATE_GB_HOUR_USD = float(os.environ.get("FARGATE_GB_HOUR_USD", "0.004445"))
EMBED_PER_1K_TOKENS_USD = float(os.environ.get("EMBED_PER_1K_TOKENS_USD", "0.00001"))
EMBED_MODEL_ID = os.environ.get("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

s3 = boto3.client("s3")
sfn = boto3.client("stepfunctions")

ERROR_STATUSES = {"ERROR", "EMPTY_TEXT", "SKIPPED_TOO_LARGE"}


def list_keys(prefix: str) -> list[str]:
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def read_json(key: str) -> dict:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return json.loads(obj["Body"].read())


def collect_file_logs(tenant: str, run_id: str) -> list[dict]:
    prefix = f"batch-poc/logs/{tenant}/{run_id}/"
    logs = []
    for key in list_keys(prefix):
        if not key.endswith(".json"):
            continue
        try:
            logs.append(read_json(key))
        except Exception:
            continue
    return logs


def collect_tanda_summaries(tenant: str, run_id: str) -> list[dict]:
    prefix = f"batch-poc/results/{tenant}/{run_id}/"
    summaries = []
    for key in sorted(list_keys(prefix)):
        if key.endswith("_summary.json"):
            summaries.append(read_json(key))
    return summaries


def estimate_embedding_tokens(tenant: str, run_id: str) -> int:
    prefix = f"embeddings-input/{tenant}/{run_id}/"
    total_chars = 0
    for key in list_keys(prefix):
        if not key.endswith(".jsonl"):
            continue
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        for line in obj["Body"].read().decode("utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            model_input = record.get("modelInput", {})
            if "inputText" in model_input:
                total_chars += len(model_input["inputText"])
            elif "texts" in model_input and model_input["texts"]:
                total_chars += len(model_input["texts"][0])
    return max(1, total_chars // 4)


def fargate_cost_usd(duration_sec: float) -> float:
    hourly = (
        FARGATE_VCPU * FARGATE_VCPU_HOUR_USD + FARGATE_MEMORY_GB * FARGATE_GB_HOUR_USD
    )
    return hourly * duration_sec / 3600


def pipeline_duration_sec(execution_arn: str | None) -> float | None:
    if not execution_arn:
        return None
    try:
        ex = sfn.describe_execution(executionArn=execution_arn)
        start = ex["startDate"]
        stop = ex.get("stopDate")
        if not stop:
            return None
        return (stop - start).total_seconds()
    except Exception:
        return None


def fmt_num(value: float | int, decimals: int = 2) -> str:
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_usd(value: float) -> str:
    if value < 0.01:
        return f"USD {value:.6f}"
    return f"USD {value:.4f}"


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes} min {secs} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min"


def build_html(report: dict) -> str:
    rows = [
        ("Cantidad original de archivos a procesar", fmt_num(report["files_requested"])),
        ("Cantidad de archivos procesados", fmt_num(report["files_processed_ok"])),
        ("Cantidad de archivos con error", fmt_num(report["files_with_error"])),
        (
            "Cantidad de chunks generados por archivo (promedio)",
            fmt_num(report["avg_chunks_per_file"], 2),
        ),
        (
            "Tiempo promedio de procesamiento por archivo",
            fmt_duration(report["avg_sec_per_file"]),
        ),
        ("Tiempo total de proceso", fmt_duration(report["total_pipeline_sec"])),
        ("Costo total del proceso", fmt_usd(report["cost_total_usd"])),
        ("Costo del modelo de embeddings", fmt_usd(report["cost_embeddings_usd"])),
        ("Costo del Extractor ECS", fmt_usd(report["cost_ecs_usd"])),
        (
            "Registros totales insertados en la base de datos",
            fmt_num(report["db_records_inserted"]),
        ),
    ]

    trs = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in rows
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <title>Reporte POC bulkrag — {html.escape(report['tenant'])}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f6f8fa; color: #1f2328; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .meta {{ color: #656d76; margin-bottom: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 720px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    th, td {{ padding: 0.85rem 1rem; text-align: left; border-bottom: 1px solid #d8dee4; }}
    th {{ width: 62%; font-weight: 600; background: #f6f8fa; }}
    td {{ font-variant-numeric: tabular-nums; }}
    .footer {{ margin-top: 2rem; font-size: 0.9rem; color: #656d76; }}
  </style>
</head>
<body>
  <h1>Reporte POC bulkrag</h1>
  <p class="meta">
    Tenant: <strong>{html.escape(report['tenant'])}</strong> ·
    Run ID: <code>{html.escape(report['run_id'])}</code> ·
    Generado: {html.escape(report['generated_at'])}
  </p>
  <table>{trs}</table>
  <p class="footer">
    Modelo embeddings: {html.escape(report['embed_model_id'])} ·
    Chunks totales: {fmt_num(report['total_chunks'])} ·
    Tareas ECS: {report['ecs_tasks']} ·
    <a href="{html.escape(report['report_json_url'])}">JSON</a>
  </p>
</body>
</html>"""


def lambda_handler(event, context):
    tenant = event["tenant"]
    run_id = event["run_id"]
    files_requested = int(event.get("total_files", 0))
    execution_arn = event.get("execution_arn")

    insert_payload = event.get("insert_result") or {}
    if isinstance(insert_payload, dict) and "Payload" in insert_payload:
        insert_payload = insert_payload["Payload"]

    logs = collect_file_logs(tenant, run_id)
    summaries = collect_tanda_summaries(tenant, run_id)

    ok_logs = [log for log in logs if log.get("status") == "OK"]
    error_logs = [log for log in logs if log.get("status") in ERROR_STATUSES]

    chunks_per_file = [log["chunks"] for log in ok_logs if log.get("chunks")]
    durations = [log["duration_sec"] for log in logs if "duration_sec" in log]

    total_chunks = sum(chunks_per_file)
    avg_chunks = total_chunks / len(chunks_per_file) if chunks_per_file else 0
    avg_sec = sum(durations) / len(durations) if durations else 0

    ecs_wall_sec = sum(s.get("wall_time_sec", 0) for s in summaries)
    ecs_tasks = len(summaries)
    cost_ecs = fargate_cost_usd(ecs_wall_sec)

    est_tokens = estimate_embedding_tokens(tenant, run_id)
    cost_embeddings = est_tokens / 1000 * EMBED_PER_1K_TOKENS_USD
    cost_total = cost_ecs + cost_embeddings

    pipeline_sec = pipeline_duration_sec(execution_arn) or ecs_wall_sec
    db_inserted = int(insert_payload.get("total_vectors_inserted", 0))

    report = {
        "tenant": tenant,
        "run_id": run_id,
        "files_requested": files_requested,
        "files_processed_ok": len(ok_logs),
        "files_with_error": len(error_logs),
        "total_chunks": total_chunks,
        "avg_chunks_per_file": round(avg_chunks, 2),
        "avg_sec_per_file": round(avg_sec, 3),
        "total_pipeline_sec": round(pipeline_sec, 1),
        "ecs_wall_sec": round(ecs_wall_sec, 1),
        "ecs_tasks": ecs_tasks,
        "estimated_embed_tokens": est_tokens,
        "cost_ecs_usd": round(cost_ecs, 6),
        "cost_embeddings_usd": round(cost_embeddings, 6),
        "cost_total_usd": round(cost_total, 6),
        "db_records_inserted": db_inserted,
        "embed_model_id": EMBED_MODEL_ID,
        "execution_arn": execution_arn or "",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    base = f"pipeline-results/{run_id}"
    json_key = f"{base}/report.json"
    html_key = f"{base}/report.html"

    s3.put_object(
        Bucket=BUCKET,
        Key=json_key,
        Body=json.dumps(report, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    s3.put_object(
        Bucket=BUCKET,
        Key=html_key,
        Body=build_html(report).encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )

    report["report_html_url"] = f"s3://{BUCKET}/{html_key}"
    report["report_json_url"] = f"s3://{BUCKET}/{json_key}"

    return report
