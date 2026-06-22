terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "ecs_extractor" {
  source = "../../modules/ecs_extractor"

  environment         = var.environment
  aws_account_id      = var.aws_account_id
  aws_region          = var.aws_region
  rag_bucket_name     = var.rag_bucket_name
  ecr_repository_name = var.ecr_repository_name
  task_cpu            = var.task_cpu
  task_memory         = var.task_memory
  worker_count        = var.worker_count
  max_file_size_mb    = var.max_file_size_mb
  vpc_id              = var.vpc_id
  subnet_ids          = var.subnet_ids
}

module "bedrock_batch" {
  source = "../../modules/bedrock_batch"

  environment     = var.environment
  aws_account_id  = var.aws_account_id
  aws_region      = var.aws_region
  rag_bucket_name = var.rag_bucket_name
}

module "bulkrag_pipeline" {
  source = "../../modules/bulkrag_pipeline"

  environment             = var.environment
  aws_account_id          = var.aws_account_id
  aws_region              = var.aws_region
  rag_bucket_name         = var.rag_bucket_name
  ecs_cluster_arn         = module.ecs_extractor.ecs_cluster_arn
  ecs_task_definition_arn = module.ecs_extractor.task_definition_arn
  ecs_subnet_ids          = var.subnet_ids
  ecs_security_group_id   = module.ecs_extractor.security_group_id
  bedrock_batch_role_arn  = module.bedrock_batch.bedrock_batch_role_arn
  skip_db_insert          = var.skip_db_insert
  aurora_cluster_arn      = var.aurora_cluster_arn
  aurora_secret_arn       = var.aurora_secret_arn
  db_name                 = var.db_name
}

module "github_oidc" {
  source = "../../modules/github_oidc"

  environment                  = var.environment
  aws_region                   = var.aws_region
  github_repository            = var.github_repository
  github_actions_environment   = var.github_actions_environment
  role_name                    = "bulkrag-github-actions-${var.environment}"
  terraform_state_bucket       = var.terraform_state_bucket
  terraform_state_lock_table   = var.terraform_state_lock_table
  rag_bucket_name              = var.rag_bucket_name
}
