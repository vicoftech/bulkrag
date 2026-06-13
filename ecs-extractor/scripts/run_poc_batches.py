"""
Script de ejecución del POC de extracción.
Uso:
  python run_poc_batches.py \
    --bucket rag-agents-prod \
    --prefix bora/2024/ \
    --cluster rag-extractor-poc-prod \
    --task-family rag-extractor-poc-prod \
    --subnets subnet-abc123 subnet-def456 \
    --security-group sg-xyz789

El script:
1. Lista 200 keys del prefix indicado en S3
2. Escribe manifests en S3: batch-poc/manifests/tanda_{1,2}.json
3. Lanza ECS Task tanda_1 en Fargate SPOT
4. Espera completion
5. Lanza ECS Task tanda_2
6. Espera completion
7. Lee summaries y muestra reporte final
"""
import argparse
import json
import sys
import time

import boto3

s3 = boto3.client("s3")
ecs = boto3.client("ecs")


def parse_args():
    p = argparse.ArgumentParser(description="POC ECS pdfplumber — run batches")
    p.add_argument("--bucket", required=True, help="Bucket S3 existente del proyecto")
    p.add_argument(
        "--prefix", required=True, help="Prefix S3 donde buscar PDFs (ej: bora/2024/)"
    )
    p.add_argument("--cluster", required=True, help="Nombre del ECS cluster")
    p.add_argument("--task-family", required=True, help="Task definition family name")
    p.add_argument("--subnets", required=True, nargs="+", help="Subnet IDs para la task")
    p.add_argument("--security-group", required=True, help="Security Group ID para la task")
    p.add_argument(
        "--total", type=int, default=200, help="Total de archivos a procesar (default: 200)"
    )
    p.add_argument(
        "--batches",
        type=int,
        default=1,
        choices=[1, 2],
        help="Cantidad de tandas ECS (default: 1; usar 2 solo para comparar batches grandes)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra keys y manifests, no lanza tasks",
    )
    return p.parse_args()


def list_pdf_keys(bucket: str, prefix: str, total: int) -> list[str]:
    """Lista hasta `total` keys de PDFs bajo el prefix dado."""
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".pdf"):
                keys.append(obj["Key"])
                if len(keys) >= total:
                    return keys
    if len(keys) < total:
        print(f"[WARN] Solo se encontraron {len(keys)} PDFs (se pedían {total})")
    return keys


def write_manifest(bucket: str, batch_num: int, keys: list[str]) -> str:
    manifest_key = f"batch-poc/manifests/tanda_{batch_num}.json"
    s3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=json.dumps({"batch": batch_num, "total": len(keys), "keys": keys}).encode(),
        ContentType="application/json",
    )
    print(
        f"[MANIFEST] tanda_{batch_num}: {len(keys)} archivos → s3://{bucket}/{manifest_key}"
    )
    return manifest_key


def get_latest_task_definition(cluster_client, family: str) -> str:
    response = cluster_client.describe_task_definition(taskDefinition=family)
    return response["taskDefinition"]["taskDefinitionArn"]


def launch_ecs_task(
    cluster: str,
    task_family: str,
    manifest_key: str,
    subnets: list[str],
    sg: str,
    bucket: str,
) -> str:
    """Lanza una ECS Fargate Spot task y retorna el task ARN."""
    task_def_arn = get_latest_task_definition(ecs, task_family)

    response = ecs.run_task(
        cluster=cluster,
        taskDefinition=task_def_arn,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": [sg],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "extractor",
                    "environment": [
                        {"name": "MANIFEST_S3_KEY", "value": manifest_key},
                        {"name": "RAG_BUCKET_NAME", "value": bucket},
                    ],
                }
            ]
        },
    )

    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS run_task falló: {failures}")

    task_arn = response["tasks"][0]["taskArn"]
    print(f"[ECS] Task lanzada: {task_arn}")
    return task_arn


def wait_for_task(cluster: str, task_arn: str, poll_seconds: int = 30) -> str:
    """Espera hasta que la task termine y retorna su exit status (SUCCESS/FAILED)."""
    print(f"[ECS] Esperando task {task_arn.split('/')[-1]}...")
    while True:
        response = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])
        task = response["tasks"][0]
        last_status = task["lastStatus"]

        if last_status == "STOPPED":
            containers = task.get("containers", [])
            exit_code = containers[0].get("exitCode", -1) if containers else -1
            stop_reason = task.get("stoppedReason", "")
            if exit_code == 0:
                print("[ECS] Task completada exitosamente.")
                return "SUCCESS"
            print(f"[ECS] Task detenida con exitCode={exit_code} reason='{stop_reason}'")
            return "FAILED"

        print(f"[ECS] Status: {last_status} — esperando {poll_seconds}s...")
        time.sleep(poll_seconds)


def print_report(bucket: str, num_batches: int) -> None:
    print("\n" + "=" * 60)
    print("REPORTE FINAL DEL POC")
    print("=" * 60)

    total_ok = total_empty = total_error = total_skipped = total_files = 0

    for n in range(1, num_batches + 1):
        summary_key = f"batch-poc/results/tanda_{n}_summary.json"
        try:
            obj = s3.get_object(Bucket=bucket, Key=summary_key)
            summary = json.loads(obj["Body"].read())
            skipped = summary.get("skipped_too_large", 0)
            print(f"\nTanda {n}:")
            print(f"  Total:      {summary['total']}")
            print(f"  OK:         {summary['ok']}")
            print(f"  EMPTY_TEXT: {summary['empty_text']}")
            print(f"  SKIPPED:    {skipped} (>{summary.get('max_file_size_mb', 30)} MB)")
            print(f"  ERRORS:     {summary['errors']}")
            wall = summary.get("wall_time_sec", summary["total_sec"])
            workers = summary.get("workers", 1)
            print(f"  Workers:    {workers}")
            print(f"  Wall time:  {wall}s")
            print(
                f"  CPU time:   {summary['total_sec']}s ({summary['avg_sec_file']}s/archivo)"
            )
            total_ok += summary["ok"]
            total_empty += summary["empty_text"]
            total_error += summary["errors"]
            total_skipped += skipped
            total_files += summary["total"]
        except Exception as e:
            print(f"\nTanda {n}: [ERROR leyendo summary] {e}")

    print(f"\nTOTAL GLOBAL: {total_files} archivos")
    print(
        f"  OK:         {total_ok} ({round(100 * total_ok / total_files, 1) if total_files else 0}%)"
    )
    print(
        f"  EMPTY_TEXT: {total_empty} ({round(100 * total_empty / total_files, 1) if total_files else 0}%)"
    )
    print(f"  SKIPPED:    {total_skipped}")
    print(f"  ERRORS:     {total_error}")
    print(f"\nOutputs:  s3://{bucket}/batch-poc/output/")
    print(f"Logs:     s3://{bucket}/batch-poc/logs/")
    print(f"Summaries:s3://{bucket}/batch-poc/results/")
    print("=" * 60)


def main():
    args = parse_args()

    print(f"[INIT] Buscando {args.total} PDFs en s3://{args.bucket}/{args.prefix}")
    all_keys = list_pdf_keys(args.bucket, args.prefix, args.total)
    if not all_keys:
        print("[ERROR] No se encontraron PDFs. Verificar bucket y prefix.")
        sys.exit(1)

    if args.batches == 2 and len(all_keys) > 1:
        mid = len(all_keys) // 2
        batches = [all_keys[:mid], all_keys[mid:]]
    else:
        batches = [all_keys]
    print(
        f"[INIT] {len(all_keys)} archivos → "
        + ", ".join(f"tanda_{i + 1}={len(b)}" for i, b in enumerate(batches))
    )

    manifest_keys = []
    for i, batch in enumerate(batches, 1):
        mk = write_manifest(args.bucket, i, batch)
        manifest_keys.append(mk)

    if args.dry_run:
        print("[DRY-RUN] Manifests escritos. No se lanzaron tasks.")
        return

    for i, manifest_key in enumerate(manifest_keys, 1):
        print(f"\n[BATCH {i}/{len(manifest_keys)}] Iniciando...")
        task_arn = launch_ecs_task(
            cluster=args.cluster,
            task_family=args.task_family,
            manifest_key=manifest_key,
            subnets=args.subnets,
            sg=args.security_group,
            bucket=args.bucket,
        )
        result = wait_for_task(args.cluster, task_arn)
        if result == "FAILED":
            print(
                f"[ERROR] Tanda {i} falló. Revisar CloudWatch: /ecs/rag-extractor-poc-*"
            )

    print_report(args.bucket, len(batches))


if __name__ == "__main__":
    main()
