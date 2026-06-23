#!/usr/bin/env bash
# Lanza el pipeline bulkrag para la muestra estratificada de 500 PDFs (boletín o anmat).
set -euo pipefail

TENANT="${1:-tenant_boletin}"
PREFIX="${2:-tenant_boletin/sample-stratified/}"
MAX_FILES="${3:-500}"
PROFILE="${AWS_PROFILE:-asap_dev}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
STATE_MACHINE="bulkrag-pipeline-dev"
NAME="${TENANT}-poc-500-$(date +%Y%m%d-%H%M%S)"

INPUT=$(cat <<EOF
{
  "tenant": "${TENANT}",
  "prefix": "${PREFIX}",
  "max_files": ${MAX_FILES},
  "files_per_manifest": 200
}
EOF
)

echo "Iniciando pipeline: ${NAME}"
echo "Input: ${INPUT}"

EXEC_ARN=$(AWS_PROFILE="${PROFILE}" AWS_DEFAULT_REGION="${REGION}" \
  aws stepfunctions start-execution \
    --state-machine-arn "arn:aws:states:${REGION}:$(aws sts get-caller-identity --query Account --output text --profile "${PROFILE}")":stateMachine:${STATE_MACHINE} \
    --name "${NAME}" \
    --input "${INPUT}" \
    --query executionArn --output text)

echo "Execution ARN: ${EXEC_ARN}"
echo ""
echo "Monitoreo:"
echo "  AWS_PROFILE=${PROFILE} aws stepfunctions describe-execution --execution-arn ${EXEC_ARN}"
echo ""
echo "Al finalizar, el reporte HTML estará en:"
echo "  s3://rag-documents-dev-615216531593/pipeline-results/<run_id>/report.html"
