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
  default = 4096
}

variable "task_memory" {
  type    = number
  default = 8192
}

variable "worker_count" {
  type        = number
  default     = 4
  description = "PDFs procesados en paralelo por task (debe ser <= vCPU asignados)"
}

variable "max_file_size_mb" {
  type        = number
  default     = 30
  description = "Tamaño máximo de PDF a procesar; archivos mayores se descartan"
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "bedrock_embed_model_id" {
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
  description = "Modelo Bedrock para embeddings (debe soportar batch en la region)"
}

variable "embed_dimensions" {
  type    = number
  default = 1024
}

variable "embed_max_chars" {
  type    = number
  default = 12000
}

variable "chunk_size_tokens" {
  type    = number
  default = 1500
}

variable "chunk_overlap_tokens" {
  type    = number
  default = 150
}
