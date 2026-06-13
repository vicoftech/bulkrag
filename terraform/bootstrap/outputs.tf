output "state_bucket_name" {
  value       = aws_s3_bucket.tfstate.id
  description = "Bucket para terraform backend"
}

output "lock_table_name" {
  value       = aws_dynamodb_table.tf_locks.name
  description = "Tabla DynamoDB para locks"
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "backend_hcl_dev" {
  description = "Snippet para terraform/envs/dev/backend.tf"
  value = <<-EOT
    terraform {
      backend "s3" {
        bucket         = "${aws_s3_bucket.tfstate.id}"
        key            = "ecs-extractor/dev/terraform.tfstate"
        region         = "${var.aws_region}"
        dynamodb_table = "${aws_dynamodb_table.tf_locks.name}"
        encrypt        = true
      }
    }
  EOT
}

output "backend_hcl_prod" {
  description = "Snippet para terraform/envs/prod/backend.tf"
  value = <<-EOT
    terraform {
      backend "s3" {
        bucket         = "${aws_s3_bucket.tfstate.id}"
        key            = "ecs-extractor/prod/terraform.tfstate"
        region         = "${var.aws_region}"
        dynamodb_table = "${aws_dynamodb_table.tf_locks.name}"
        encrypt        = true
      }
    }
  EOT
}
