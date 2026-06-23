locals {
  lambda_names = {
    list_manifests      = "bulkrag_list_manifests"
    consolidate_chunks  = "bulkrag_consolidate_chunks"
    insert_pgvector     = "bulkrag_insert_pgvector"
    run_bedrock_batch   = "bulkrag_run_bedrock_batch"
    generate_report     = "bulkrag_generate_report"
  }
}

resource "aws_lambda_function" "list_manifests" {
  function_name    = "${local.lambda_names.list_manifests}_${var.environment}"
  role             = aws_iam_role.bulkrag_lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 512
  filename         = "${path.module}/../../../lambdas/bulkrag_list_manifests/dist/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../../lambdas/bulkrag_list_manifests/dist/lambda.zip")

  environment {
    variables = {
      RAG_BUCKET_NAME = var.rag_bucket_name
    }
  }
}

resource "aws_lambda_function" "consolidate_chunks" {
  function_name    = "${local.lambda_names.consolidate_chunks}_${var.environment}"
  role             = aws_iam_role.bulkrag_lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 600
  memory_size      = 1024
  filename         = "${path.module}/../../../lambdas/bulkrag_consolidate_chunks/dist/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../../lambdas/bulkrag_consolidate_chunks/dist/lambda.zip")

  environment {
    variables = {
      RAG_BUCKET_NAME = var.rag_bucket_name
    }
  }
}

resource "aws_lambda_function" "insert_pgvector" {
  function_name    = "${local.lambda_names.insert_pgvector}_${var.environment}"
  role             = aws_iam_role.bulkrag_lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 1024
  filename         = "${path.module}/../../../lambdas/bulkrag_insert_pgvector/dist/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../../lambdas/bulkrag_insert_pgvector/dist/lambda.zip")

  dynamic "vpc_config" {
    for_each = local.aurora_enabled ? [1] : []
    content {
      subnet_ids         = var.aurora_subnet_ids
      security_group_ids = [aws_security_group.insert_pgvector_lambda[0].id]
    }
  }

  environment {
    variables = {
      RAG_BUCKET_NAME   = var.rag_bucket_name
      AURORA_SECRET_ARN = local.aurora_secret_arn
      SKIP_DB_INSERT    = local.db_insert_disabled ? "true" : "false"
    }
  }
}

resource "aws_lambda_function" "generate_report" {
  function_name    = "${local.lambda_names.generate_report}_${var.environment}"
  role             = aws_iam_role.bulkrag_lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 512
  filename         = "${path.module}/../../../lambdas/bulkrag_generate_report/dist/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../../lambdas/bulkrag_generate_report/dist/lambda.zip")

  environment {
    variables = {
      RAG_BUCKET_NAME        = var.rag_bucket_name
      BEDROCK_EMBED_MODEL_ID = var.bedrock_embed_model_id
    }
  }
}

resource "aws_lambda_function" "run_bedrock_batch" {
  function_name    = "${local.lambda_names.run_bedrock_batch}_${var.environment}"
  role             = aws_iam_role.bulkrag_lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 512
  filename         = "${path.module}/../../../lambdas/bulkrag_run_bedrock_batch/dist/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../../lambdas/bulkrag_run_bedrock_batch/dist/lambda.zip")

  environment {
    variables = {
      BEDROCK_BATCH_ROLE_ARN = var.bedrock_batch_role_arn
      BEDROCK_EMBED_MODEL_ID = var.bedrock_embed_model_id
    }
  }
}
