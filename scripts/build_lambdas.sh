#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

build_lambda() {
  local name="$1"
  local dir="$ROOT/lambdas/$name"
  local out="$dir/dist/lambda.zip"

  mkdir -p "$dir/dist"
  rm -rf "$dir/dist/build"
  mkdir -p "$dir/dist/build"

  if [[ "$name" == "bulkrag_insert_pgvector" ]]; then
    pip install -q -r "$dir/requirements.txt" -t "$dir/dist/build" \
      --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12
  else
    pip install -q -r "$dir/requirements.txt" -t "$dir/dist/build"
  fi

  cp "$dir/handler.py" "$dir/dist/build/"
  (cd "$dir/dist/build" && zip -qr "$out" .)
  echo "Built $out"
}

build_lambda bulkrag_list_manifests
build_lambda bulkrag_consolidate_chunks
build_lambda bulkrag_insert_pgvector
build_lambda bulkrag_run_bedrock_batch
build_lambda bulkrag_generate_report
