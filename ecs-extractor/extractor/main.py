"""
RAG ECS Extractor — POC
Recibe: MANIFEST_S3_KEY (env var) → lista de S3 keys de PDFs
Produce: texto extraído en batch-poc/output/ y logs en batch-poc/logs/
"""
import io
import json
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

import boto3
import pdfplumber

BUCKET = os.environ["RAG_BUCKET_NAME"]
MANIFEST_KEY = os.environ["MANIFEST_S3_KEY"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
WORKER_COUNT = int(os.environ.get("WORKER_COUNT", os.cpu_count() or 1))
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "30"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

s3 = boto3.client("s3", region_name=REGION)


def read_manifest() -> list[str]:
    obj = s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
    data = json.loads(obj["Body"].read())
    return data["keys"]


def _extract_text_from_bytes(pdf_bytes: bytes) -> tuple[str, str]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages_text = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
        full_text = "\n\n".join(pages_text)

    if not full_text.strip():
        return "", "EMPTY_TEXT"
    return full_text, "OK"


def _write_log(
    worker_s3,
    bucket: str,
    pdf_key: str,
    status: str,
    duration_sec: float,
    error: str = "",
    size_bytes: int | None = None,
) -> None:
    payload = {
        "key": pdf_key,
        "status": status,
        "duration_sec": round(duration_sec, 2),
        "error": error,
    }
    if size_bytes is not None:
        payload["size_bytes"] = size_bytes
        payload["max_size_bytes"] = MAX_FILE_SIZE_BYTES

    worker_s3.put_object(
        Bucket=bucket,
        Key=f"batch-poc/logs/{pdf_key}.json",
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )


def _process_pdf(bucket: str, region: str, pdf_key: str) -> dict:
    """Procesa un PDF de punta a punta en un worker (download → extract → upload)."""
    worker_s3 = boto3.client("s3", region_name=region)
    t0 = time.time()

    try:
        head = worker_s3.head_object(Bucket=bucket, Key=pdf_key)
        size_bytes = head["ContentLength"]

        if size_bytes > MAX_FILE_SIZE_BYTES:
            duration = round(time.time() - t0, 2)
            _write_log(
                worker_s3,
                bucket,
                pdf_key,
                "SKIPPED_TOO_LARGE",
                duration,
                error=f"File exceeds {MAX_FILE_SIZE_MB} MB limit",
                size_bytes=size_bytes,
            )
            return {
                "key": pdf_key,
                "status": "SKIPPED_TOO_LARGE",
                "duration_sec": duration,
                "size_bytes": size_bytes,
            }

        obj = worker_s3.get_object(Bucket=bucket, Key=pdf_key)
        pdf_bytes = obj["Body"].read()
        text, status = _extract_text_from_bytes(pdf_bytes)

        if status == "OK":
            worker_s3.put_object(
                Bucket=bucket,
                Key=f"batch-poc/output/{pdf_key}.txt",
                Body=text.encode("utf-8"),
                ContentType="text/plain",
            )

        duration = round(time.time() - t0, 2)
        _write_log(worker_s3, bucket, pdf_key, status, duration, size_bytes=size_bytes)
        return {"key": pdf_key, "status": status, "duration_sec": duration}
    except Exception:
        duration = round(time.time() - t0, 2)
        err_msg = traceback.format_exc()
        _write_log(worker_s3, bucket, pdf_key, "ERROR", duration, error=err_msg[:500])
        return {"key": pdf_key, "status": "ERROR", "duration_sec": duration}


def write_summary(
    manifest_key: str, results: list[dict], wall_time_sec: float, workers: int
) -> None:
    base = manifest_key.split("/")[-1].replace(".json", "")
    summary_key = f"batch-poc/results/{base}_summary.json"

    ok_count = sum(1 for r in results if r["status"] == "OK")
    empty_count = sum(1 for r in results if r["status"] == "EMPTY_TEXT")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    skipped_count = sum(1 for r in results if r["status"] == "SKIPPED_TOO_LARGE")
    total_sec = sum(r["duration_sec"] for r in results)

    s3.put_object(
        Bucket=BUCKET,
        Key=summary_key,
        Body=json.dumps(
            {
                "manifest": manifest_key,
                "total": len(results),
                "ok": ok_count,
                "empty_text": empty_count,
                "errors": error_count,
                "skipped_too_large": skipped_count,
                "max_file_size_mb": MAX_FILE_SIZE_MB,
                "workers": workers,
                "wall_time_sec": round(wall_time_sec, 2),
                "total_sec": round(total_sec, 2),
                "avg_sec_file": round(total_sec / len(results), 2) if results else 0,
                "results": results,
            },
            indent=2,
        ).encode("utf-8"),
        ContentType="application/json",
    )
    print(
        f"[SUMMARY] OK={ok_count} EMPTY={empty_count} ERROR={error_count} "
        f"SKIPPED={skipped_count} wall_time={round(wall_time_sec, 1)}s "
        f"workers={workers} summary_key={summary_key}"
    )


def main():
    keys = read_manifest()
    workers = max(1, min(WORKER_COUNT, len(keys)))
    print(
        f"[START] manifest={MANIFEST_KEY} bucket={BUCKET} "
        f"files={len(keys)} workers={workers} max_size_mb={MAX_FILE_SIZE_MB}"
    )

    results = []
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_pdf, BUCKET, REGION, key): key for key in keys
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            results.append(result)
            print(
                f"[{done}/{len(keys)}] {result['status']} {result['key']} "
                f"({result['duration_sec']}s)"
            )

    wall_time_sec = time.time() - t0
    results.sort(key=lambda r: keys.index(r["key"]))
    write_summary(MANIFEST_KEY, results, wall_time_sec, workers)
    print("[END]")


if __name__ == "__main__":
    main()
