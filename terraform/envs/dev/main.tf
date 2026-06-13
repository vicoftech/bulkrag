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
  vpc_id              = var.vpc_id
  subnet_ids          = var.subnet_ids
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
