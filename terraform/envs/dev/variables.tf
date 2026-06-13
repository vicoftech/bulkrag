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
