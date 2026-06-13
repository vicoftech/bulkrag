# Terraform Remote State — bulkrag (independiente)

Backend remoto **propio** del proyecto en cuenta **asap_dev** (`615216531593`).

## Recursos

| Recurso | Valor |
|---------|-------|
| Bucket S3 | `bulkrag-terraform-state-615216531593` |
| Tabla DynamoDB | `bulkrag-terraform-locks` |
| State dev | `ecs-extractor/dev/terraform.tfstate` |
| State prod | `ecs-extractor/prod/terraform.tfstate` |
| OIDC Role | `bulkrag-github-actions-dev` |

## Bootstrap (una sola vez)

```bash
cd terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
AWS_PROFILE=asap_dev terraform init
AWS_PROFILE=asap_dev terraform apply
```

## Uso diario

```bash
cd terraform/envs/dev
AWS_PROFILE=asap_dev terraform init
AWS_PROFILE=asap_dev terraform plan
```

Ver spec completa: `docs/terraform-remote-state.mdc`
