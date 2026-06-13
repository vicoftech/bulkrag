variable "environment" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "github_repository" {
  type        = string
  description = "Repositorio GitHub en formato org/repo (ej: vicoftech/bulkrag)"
}

variable "github_actions_environment" {
  type        = string
  default     = "development"
  description = "Nombre del GitHub Environment (debe coincidir con environment: en el workflow)"
}

variable "role_name" {
  type        = string
  description = "Nombre del IAM Role para GitHub Actions"
}

variable "terraform_state_bucket" {
  type = string
}

variable "terraform_state_lock_table" {
  type = string
}

variable "rag_bucket_name" {
  type = string
}
