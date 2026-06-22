"""
Bulkrag ECS Extractor — extracción + chunking opcional para pipeline RAG.
Modo POC: solo MANIFEST_S3_KEY → output/logs legacy.
Modo pipeline: TENANT + RUN_ID → output, logs, pending-embeddings con chunking.
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
TENANT = os.environ.get("TENANT", "")
RUN_ID = os.environ.get("RUN_ID", "")
PIPELINE_MODE = bool(TENANT and RUN_ID)
REGION = os.environ.get("AWS_REGION", "us-east-1")
WORKER_COUNT = int(os.environ.get("WORKER_COUNT", os.cpu_count() or 1))
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "30"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE_TOKENS", "1500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "150"))
BEDROCK_EMBED_MODEL_ID = os.environ.get(
    "BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"
)
EMBED_DIMENSIONS = int(os.environ.get("EMBED_DIMENSIONS", "1024"))
EMBED_MAX_CHARS = int(os.environ.get("EMBED_MAX_CHARS", "12000"))

s3 = boto3.client("s3", region_name=REGION)


def read_manifest() -> list[str]:
    obj = s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
    data = json.loads(obj["Body"].read())
    return data["keys"]


def _model_input_for_chunk(chunk: str) -> dict:
    if "cohere" in BEDROCK_EMBED_MODEL_ID:
        return {"texts": [chunk], "input_type": "search_document"}
    return {
        "inputText": chunk,
        "dimensions": EMBED_DIMENSIONS,
        "normalize": True,
    }


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Chunking por caracteres (~4 chars/token, capped por modelo de embedding)."""
    max_chars = min(chunk_size * 4, EMBED_MAX_CHARS)
    overlap_chars = min(overlap * 4, max_chars // 5)
    if not text.strip():
        return []

    chunks = []
    start = 0
    step = max(max_chars - overlap_chars, 1)
    while start < len(text):
        chunk = text[start : start + max_chars].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def _log_key(pdf_key: str) -> str:
    if PIPELINE_MODE:
        return f"batch-poc/logs/{TENANT}/{RUN_ID}/{pdf_key}.json"
    return f"batch-poc/logs/{pdf_key}.json"


def _output_key(pdf_key: str) -> str:
    if PIPELINE_MODE:
        return f"batch-poc/output/{TENANT}/{RUN_ID}/{pdf_key}.txt"
    return f"batch-poc/output/{pdf_key}.txt"


def _pending_embeddings_key(pdf_key: str) -> str:
    return f"pending-embeddings/{TENANT}/{RUN_ID}/{pdf_key}.jsonl"


def _write_log(
    worker_s3,
    bucket: str,
    pdf_key: str,
    status: str,
    duration_sec: float,
    error: str = "",
    size_bytes: int | None = None,
    chunks: int | None = None,
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
    if chunks is not None:
        payload["chunks"] = chunks
    if PIPELINE_MODE:
        payload["tenant"] = TENANT
        payload["run_id"] = RUN_ID

    worker_s3.put_object(
        Bucket=bucket,
        Key=_log_key(pdf_key),
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )


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


def _write_chunks_jsonl(worker_s3, bucket: str, pdf_key: str, full_text: str) -> int:
    chunks = chunk_text(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        return 0

    lines = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{pdf_key}::chunk_{i:04d}"
        lines.append(
            json.dumps(
                {
                    "recordId": chunk_id,
                    "modelInput": _model_input_for_chunk(chunk),
                    "_meta": {
                        "source_key": pdf_key,
                        "chunk_index": i,
                        "tenant": TENANT,
                    },
                }
            )
        )

    worker_s3.put_object(
        Bucket=bucket,
        Key=_pending_embeddings_key(pdf_key),
        Body="\n".join(lines).encode("utf-8"),
        ContentType="application/x-ndjson",
    )
    return len(chunks)


def _process_pdf(bucket: str, region: str, pdf_key: str) -> dict:
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
        num_chunks = 0

        if status == "OK":
            worker_s3.put_object(
                Bucket=bucket,
                Key=_output_key(pdf_key),
                Body=text.encode("utf-8"),
                ContentType="text/plain",
            )
            if PIPELINE_MODE:
                num_chunks = _write_chunks_jsonl(worker_s3, bucket, pdf_key, text)

        duration = round(time.time() - t0, 2)
        _write_log(
            worker_s3,
            bucket,
            pdf_key,
            status,
            duration,
            size_bytes=size_bytes,
            chunks=num_chunks if status == "OK" else None,
        )
        result = {"key": pdf_key, "status": status, "duration_sec": duration}
        if num_chunks:
            result["chunks"] = num_chunks
        return result
    except Exception:
        duration = round(time.time() - t0, 2)
        err_msg = traceback.format_exc()
        _write_log(worker_s3, bucket, pdf_key, "ERROR", duration, error=err_msg[:500])
        return {"key": pdf_key, "status": "ERROR", "duration_sec": duration}


def write_summary(
    manifest_key: str, results: list[dict], wall_time_sec: float, workers: int
) -> None:
    base = manifest_key.split("/")[-1].replace(".json", "")
    if PIPELINE_MODE:
        summary_key = f"batch-poc/results/{TENANT}/{RUN_ID}/{base}_summary.json"
    else:
        summary_key = f"batch-poc/results/{base}_summary.json"

    ok_count = sum(1 for r in results if r["status"] == "OK")
    empty_count = sum(1 for r in results if r["status"] == "EMPTY_TEXT")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    skipped_count = sum(1 for r in results if r["status"] == "SKIPPED_TOO_LARGE")
    total_sec = sum(r["duration_sec"] for r in results)
    total_chunks = sum(r.get("chunks", 0) for r in results)

    summary = {
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
    }
    if PIPELINE_MODE:
        summary["tenant"] = TENANT
        summary["run_id"] = RUN_ID
        summary["total_chunks"] = total_chunks

    s3.put_object(
        Bucket=BUCKET,
        Key=summary_key,
        Body=json.dumps(summary, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    print(
        f"[SUMMARY] OK={ok_count} EMPTY={empty_count} ERROR={error_count} "
        f"SKIPPED={skipped_count} chunks={total_chunks} "
        f"wall_time={round(wall_time_sec, 1)}s workers={workers} "
        f"summary_key={summary_key}"
    )


def main():
    keys = read_manifest()
    workers = max(1, min(WORKER_COUNT, len(keys)))
    mode = "pipeline" if PIPELINE_MODE else "poc"
    print(
        f"[START] mode={mode} manifest={MANIFEST_KEY} bucket={BUCKET} "
        f"tenant={TENANT or '-'} run_id={RUN_ID or '-'} "
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
