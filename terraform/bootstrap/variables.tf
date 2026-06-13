variable "aws_region" {
  type        = string
  description = "Región AWS"
  default     = "us-east-1"
}

variable "aws_profile" {
  type        = string
  description = "Perfil AWS CLI para apply local (vacío = cadena por defecto)"
  default     = "asap_dev"
}

variable "project_name" {
  type        = string
  description = "Nombre del proyecto (tags y naming)"
  default     = "bulkrag"
}

variable "state_bucket_name" {
  type        = string
  description = "Nombre globalmente único del bucket de estado"
  default     = ""
}

variable "lock_table_name" {
  type        = string
  description = "Tabla DynamoDB para bloqueo de estado"
  default     = "bulkrag-terraform-locks"
}
