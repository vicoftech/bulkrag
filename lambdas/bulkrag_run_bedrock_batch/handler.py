"""Step 4: genera embeddings vía Bedrock (batch si está disponible, invokeModel si no)."""
import json
import os
import time

import boto3

BEDROCK_BATCH_ROLE_ARN = os.environ["BEDROCK_BATCH_ROLE_ARN"]
MODEL_ID = os.environ.get("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
POLL_INTERVAL_SEC = int(os.environ.get("BEDROCK_POLL_INTERVAL_SEC", "30"))
MAX_WAIT_SEC = int(os.environ.get("BEDROCK_MAX_WAIT_SEC", "3600"))
MIN_BATCH_RECORDS = int(os.environ.get("BEDROCK_MIN_BATCH_RECORDS", "100"))

bedrock = boto3.client("bedrock")
bedrock_runtime = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")


def _job_name(tenant: str, run_id: str, batch_index: int) -> str:
    safe_tenant = tenant.replace("_", "-")
    safe_run_id = run_id.replace("_", "-")
    suffix = int(time.time()) % 1_000_000
    return f"bulkrag-{safe_tenant}-{safe_run_id}-b{batch_index}-{suffix}"[:63]


def _count_input_records(bucket: str, input_key: str) -> int:
    obj = s3.get_object(Bucket=bucket, Key=input_key)
    return sum(
        1
        for line in obj["Body"].read().decode("utf-8").splitlines()
        if line.strip()
    )


def _invoke_sync_embeddings(bucket: str, input_key: str, output_uri: str) -> dict:
    obj = s3.get_object(Bucket=bucket, Key=input_key)
    lines = [line for line in obj["Body"].read().decode("utf-8").splitlines() if line.strip()]

    output_lines = []
    for line in lines:
        record = json.loads(line)
        record_id = record["recordId"]
        model_input = record["modelInput"]
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(model_input).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        model_output = json.loads(response["body"].read())
        output_lines.append(
            json.dumps({"recordId": record_id, "modelOutput": model_output})
        )

    # output_uri: s3://bucket/prefix/
    without_scheme = output_uri.removeprefix("s3://")
    bucket_name, _, prefix = without_scheme.partition("/")
    output_key = f"{prefix.rstrip('/')}/output.jsonl.out"
    s3.put_object(
        Bucket=bucket_name,
        Key=output_key,
        Body="\n".join(output_lines).encode("utf-8"),
    )

    return {
        "mode": "invokeModel",
        "records": len(output_lines),
        "output_key": output_key,
    }


def _run_batch_job(job_name: str, input_uri: str, output_uri: str) -> dict:
    response = bedrock.create_model_invocation_job(
        jobName=job_name,
        modelId=MODEL_ID,
        roleArn=BEDROCK_BATCH_ROLE_ARN,
        inputDataConfig={"s3InputDataConfig": {"s3Uri": input_uri}},
        outputDataConfig={"s3OutputDataConfig": {"s3Uri": output_uri}},
    )
    job_arn = response["jobArn"]

    deadline = time.time() + MAX_WAIT_SEC
    status = "InProgress"
    while status in ("Submitted", "InProgress", "Validating") and time.time() < deadline:
        time.sleep(POLL_INTERVAL_SEC)
        job = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
        status = job["status"]

    if status != "Completed":
        message = ""
        try:
            job = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
            message = job.get("message", "")
        except Exception:
            pass
        raise RuntimeError(
            f"Bedrock batch job {job_arn} terminó con status={status} message={message}"
        )

    return {"mode": "batch", "job_arn": job_arn, "status": status}


def lambda_handler(event, context):
    bucket = event["bucket"]
    tenant = event["tenant"]
    run_id = event["run_id"]
    input_key = event["input_key"]
    batch_index = event.get("batch_index", 0)

    job_name = _job_name(tenant, run_id, batch_index)
    input_uri = f"s3://{bucket}/{input_key}"
    output_uri = f"s3://{bucket}/embeddings-output/{tenant}/{run_id}/batch_{batch_index}/"

    record_count = _count_input_records(bucket, input_key)
    if record_count < MIN_BATCH_RECORDS:
        result = _invoke_sync_embeddings(bucket, input_key, output_uri)
        result["batch_skipped_reason"] = (
            f"records={record_count} < min_batch={MIN_BATCH_RECORDS}"
        )
    else:
        try:
            result = _run_batch_job(job_name, input_uri, output_uri)
        except bedrock.exceptions.ValidationException as exc:
            if "Batch inference is not supported" not in str(exc):
                raise
            result = _invoke_sync_embeddings(bucket, input_key, output_uri)
            result["batch_skipped_reason"] = "model_no_batch_support"

    return {
        "job_name": job_name,
        "output_uri": output_uri,
        "batch_index": batch_index,
        "record_count": record_count,
        **result,
    }
