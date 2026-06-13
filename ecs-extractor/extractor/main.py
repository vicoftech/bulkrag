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

import boto3
import pdfplumber

BUCKET = os.environ["RAG_BUCKET_NAME"]
MANIFEST_KEY = os.environ["MANIFEST_S3_KEY"]
REGION = os.environ.get("AWS_REGION", "us-east-1")

s3 = boto3.client("s3", region_name=REGION)


def read_manifest() -> list[str]:
    obj = s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
    data = json.loads(obj["Body"].read())
    return data["keys"]


def extract_text(pdf_key: str) -> tuple[str, str]:
    """
    Retorna (texto, status) donde status es:
      OK          → texto extraído correctamente
      EMPTY_TEXT  → PDF sin texto digital (probable scan)
      ERROR       → excepción durante extracción
    """
    obj = s3.get_object(Bucket=BUCKET, Key=pdf_key)
    pdf_bytes = obj["Body"].read()

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


def write_output(pdf_key: str, text: str) -> None:
    output_key = f"batch-poc/output/{pdf_key}.txt"
    s3.put_object(
        Bucket=BUCKET,
        Key=output_key,
        Body=text.encode("utf-8"),
        ContentType="text/plain",
    )


def write_log(pdf_key: str, status: str, duration_sec: float, error: str = "") -> None:
    log_key = f"batch-poc/logs/{pdf_key}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=log_key,
        Body=json.dumps(
            {
                "key": pdf_key,
                "status": status,
                "duration_sec": round(duration_sec, 2),
                "error": error,
            }
        ).encode("utf-8"),
        ContentType="application/json",
    )


def write_summary(manifest_key: str, results: list[dict]) -> None:
    base = manifest_key.split("/")[-1].replace(".json", "")
    summary_key = f"batch-poc/results/{base}_summary.json"

    ok_count = sum(1 for r in results if r["status"] == "OK")
    empty_count = sum(1 for r in results if r["status"] == "EMPTY_TEXT")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
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
        f"total_time={round(total_sec, 1)}s summary_key={summary_key}"
    )


def main():
    print(f"[START] manifest={MANIFEST_KEY} bucket={BUCKET}")
    keys = read_manifest()
    results = []

    for i, key in enumerate(keys, 1):
        t0 = time.time()
        try:
            text, status = extract_text(key)
            if status == "OK":
                write_output(key, text)
            write_log(key, status, time.time() - t0)
            results.append(
                {
                    "key": key,
                    "status": status,
                    "duration_sec": round(time.time() - t0, 2),
                }
            )
            print(f"[{i}/{len(keys)}] {status} {key} ({round(time.time() - t0, 2)}s)")
        except Exception as e:
            duration = time.time() - t0
            err_msg = traceback.format_exc()
            write_log(key, "ERROR", duration, error=err_msg[:500])
            results.append(
                {"key": key, "status": "ERROR", "duration_sec": round(duration, 2)}
            )
            print(f"[{i}/{len(keys)}] ERROR {key}: {e}")

    write_summary(MANIFEST_KEY, results)
    print("[END]")


if __name__ == "__main__":
    main()
