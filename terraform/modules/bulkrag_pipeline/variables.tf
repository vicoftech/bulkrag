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

variable "aurora_secret_arn" {
  type    = string
  default = ""
}

variable "aurora_cluster_arn" {
  type    = string
  default = ""
}

variable "db_name" {
  type    = string
  default = ""
}

variable "skip_db_insert" {
  type    = bool
  default = true
}
