variable "environment" {
  type    = string
  default = "dev"
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

variable "ecr_repository_name" {
  type    = string
  default = "rag-ecs-extractor"
}

variable "task_cpu" {
  type    = number
  default = 4096
}

variable "task_memory" {
  type    = number
  default = 8192
}

variable "worker_count" {
  type    = number
  default = 4
}

variable "max_file_size_mb" {
  type    = number
  default = 30
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "github_repository" {
  type        = string
  description = "Repositorio GitHub org/repo"
}

variable "github_actions_environment" {
  type    = string
  default = "development"
}

variable "terraform_state_bucket" {
  type = string
}

variable "terraform_state_lock_table" {
  type = string
}

variable "skip_db_insert" {
  type    = bool
  default = true
}

variable "aurora_cluster_arn" {
  type    = string
  default = ""
}

variable "aurora_secret_arn" {
  type    = string
  default = ""
}

variable "db_name" {
  type    = string
  default = ""
}
