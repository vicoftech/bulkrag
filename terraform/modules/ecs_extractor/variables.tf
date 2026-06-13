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
  type        = string
  description = "Bucket S3 existente del proyecto rag-agents"
}

variable "ecr_repository_name" {
  type    = string
  default = "rag-ecs-extractor"
}

variable "task_cpu" {
  type    = number
  default = 1024
}

variable "task_memory" {
  type    = number
  default = 2048
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}
