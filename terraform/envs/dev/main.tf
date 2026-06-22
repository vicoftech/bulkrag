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

  environment            = var.environment
  aws_account_id         = var.aws_account_id
  aws_region             = var.aws_region
  rag_bucket_name        = var.rag_bucket_name
  ecr_repository_name    = var.ecr_repository_name
  task_cpu               = var.task_cpu
  task_memory            = var.task_memory
  worker_count           = var.worker_count
  max_file_size_mb       = var.max_file_size_mb
  vpc_id                 = var.vpc_id
  subnet_ids             = var.subnet_ids
  bedrock_embed_model_id = var.bedrock_embed_model_id
}

module "bedrock_batch" {
  source = "../../modules/bedrock_batch"

  environment            = var.environment
  aws_account_id         = var.aws_account_id
  aws_region             = var.aws_region
  rag_bucket_name        = var.rag_bucket_name
  bedrock_embed_model_id = var.bedrock_embed_model_id
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
  bedrock_batch_role_arn        = module.bedrock_batch.bedrock_batch_role_arn
  bedrock_embed_model_id        = var.bedrock_embed_model_id
  skip_db_insert                = var.skip_db_insert
  aurora_host                   = var.aurora_host
  aurora_db_name                = var.aurora_db_name
  aurora_db_user                = var.aurora_db_user
  aurora_db_password            = var.aurora_db_password
  aurora_vpc_id                 = var.aurora_vpc_id
  aurora_subnet_ids             = var.aurora_subnet_ids
  aurora_security_group_id      = var.aurora_security_group_id
  aurora_existing_secret_arn    = var.aurora_existing_secret_arn
  aurora_vpce_security_group_id = var.aurora_vpce_security_group_id
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
