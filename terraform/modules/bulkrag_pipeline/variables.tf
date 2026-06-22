variable "environment" {
  type = string
}

variable "aws_account_id" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "rag_bucket_name" {
  type = string
}

variable "ecs_cluster_arn" {
  type = string
}

variable "ecs_task_definition_arn" {
  type = string
}

variable "ecs_subnet_ids" {
  type = list(string)
}

variable "ecs_security_group_id" {
  type = string
}

variable "bedrock_batch_role_arn" {
  type = string
}

variable "bedrock_embed_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}

variable "aurora_secret_arn" {
  type    = string
  default = ""
}

variable "aurora_cluster_arn" {
  type    = string
  default = ""
}

variable "aurora_host" {
  type    = string
  default = ""
}

variable "aurora_db_name" {
  type    = string
  default = ""
}

variable "aurora_db_user" {
  type    = string
  default = "postgres"
}

variable "aurora_db_password" {
  type      = string
  sensitive = true
  default   = ""
}

variable "aurora_vpc_id" {
  type    = string
  default = ""
}

variable "aurora_subnet_ids" {
  type    = list(string)
  default = []
}

variable "aurora_security_group_id" {
  type    = string
  default = ""
}

variable "aurora_existing_secret_arn" {
  type    = string
  default = ""
}

variable "aurora_vpce_security_group_id" {
  type    = string
  default = ""
}

variable "skip_db_insert" {
  type    = bool
  default = false
}

locals {
  use_existing_secret = var.aurora_existing_secret_arn != ""
  aurora_enabled      = var.aurora_host != "" && (var.aurora_db_password != "" || local.use_existing_secret)
  create_secret       = local.aurora_enabled && !local.use_existing_secret
  aurora_secret_arn   = local.use_existing_secret ? var.aurora_existing_secret_arn : (local.create_secret ? aws_secretsmanager_secret.aurora[0].arn : var.aurora_secret_arn)
  db_insert_disabled  = var.skip_db_insert || !local.aurora_enabled
}
