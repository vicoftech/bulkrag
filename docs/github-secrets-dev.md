# GitHub Secrets — entorno `development` (cuenta asap_dev 615216531593)

Proyecto **independiente** con state y OIDC propios de bulkrag.

Configurar en el repo: **Settings → Secrets and variables → Actions → Environment `development`**.

---

## 1. Secrets (Environment `development`)

| Key | Value |
|-----|-------|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::615216531593:role/bulkrag-github-actions-dev` |

---

## 2. Variables (Settings → Variables → Actions)

| Key | Value |
|-----|-------|
| `AWS_REGION` | `us-east-1` |
| `RAG_BUCKET_NAME` | `rag-documents-dev-615216531593` |
| `ECS_CLUSTER_NAME` | `rag-extractor-poc-dev` |
| `ECS_TASK_FAMILY` | `rag-extractor-poc-dev` |
| `ECS_SUBNETS` | `subnet-05adff7c61ea0ac0a,subnet-06e71711cc39c6112` |
| `ECS_SECURITY_GROUP` | `sg-0eb719c176f522272` |

---

## 3. OIDC — condición de trust

```
repo:vicoftech/bulkrag:environment:development
```

- OIDC Provider: compartido a nivel cuenta (`token.actions.githubusercontent.com`)
- IAM Role: **propio de bulkrag** → `bulkrag-github-actions-dev`

---

## 4. Terraform State (propio de bulkrag)

| Recurso | Valor |
|---------|-------|
| Bucket S3 | `bulkrag-terraform-state-615216531593` |
| Tabla DynamoDB | `bulkrag-terraform-locks` |
| State dev | `ecs-extractor/dev/terraform.tfstate` |
| State prod | `ecs-extractor/prod/terraform.tfstate` |

---

## 5. Secret opcional `DEV_TFVARS`

```hcl
environment                = "dev"
aws_account_id             = "615216531593"
aws_region                 = "us-east-1"
rag_bucket_name            = "rag-documents-dev-615216531593"
vpc_id                     = "vpc-032f6456c496846a0"
subnet_ids                 = ["subnet-05adff7c61ea0ac0a", "subnet-06e71711cc39c6112"]
github_repository          = "vicoftech/bulkrag"
github_actions_environment = "development"
terraform_state_bucket     = "bulkrag-terraform-state-615216531593"
terraform_state_lock_table = "bulkrag-terraform-locks"
```

---

## 6. Comando POC local (profile asap_dev)

```bash
python ecs-extractor/scripts/run_poc_batches.py \
  --bucket rag-documents-dev-615216531593 \
  --prefix tenant_boletin/ \
  --cluster rag-extractor-poc-dev \
  --task-family rag-extractor-poc-dev \
  --subnets subnet-05adff7c61ea0ac0a subnet-06e71711cc39c6112 \
  --security-group sg-0eb719c176f522272 \
  --dry-run
```
