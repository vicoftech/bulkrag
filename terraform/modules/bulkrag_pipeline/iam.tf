resource "aws_iam_role" "bulkrag_lambda_role" {
  name = "bulkrag-lambda-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.bulkrag_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "bulkrag-lambda-s3-policy"
  role = aws_iam_role.bulkrag_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = [
        "arn:aws:s3:::${var.rag_bucket_name}",
        "arn:aws:s3:::${var.rag_bucket_name}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_rds_data" {
  count = var.aurora_cluster_arn != "" ? 1 : 0
  name  = "bulkrag-lambda-rds-data-policy"
  role  = aws_iam_role.bulkrag_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["rds-data:BatchExecuteStatement", "rds-data:ExecuteStatement"]
        Resource = var.aurora_cluster_arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.aurora_secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "bulkrag-lambda-bedrock-policy"
  role = aws_iam_role.bulkrag_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:CreateModelInvocationJob",
          "bedrock:GetModelInvocationJob",
          "bedrock:StopModelInvocationJob",
          "bedrock:InvokeModel"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = var.bedrock_batch_role_arn
      },
      {
        Effect = "Allow"
        Action = [
          "aws-marketplace:Subscribe",
          "aws-marketplace:Unsubscribe",
          "aws-marketplace:ViewSubscriptions"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role" "step_functions_role" {
  name = "bulkrag-step-functions-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "step_functions_permissions" {
  name = "bulkrag-step-functions-policy"
  role = aws_iam_role.step_functions_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.list_manifests.arn,
          aws_lambda_function.consolidate_chunks.arn,
          aws_lambda_function.insert_pgvector.arn,
          aws_lambda_function.run_bedrock_batch.arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask", "ecs:StopTask", "ecs:DescribeTasks"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = "*"
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["events:PutTargets", "events:PutRule", "events:DescribeRule"]
        Resource = "arn:aws:events:${var.aws_region}:${var.aws_account_id}:rule/StepFunctionsGetEventsForECSTaskRule"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:CreateModelInvocationJob",
          "bedrock:GetModelInvocationJob",
          "bedrock:StopModelInvocationJob"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = var.bedrock_batch_role_arn
      },
      {
        Effect   = "Allow"
        Action   = ["events:PutTargets", "events:PutRule", "events:DescribeRule"]
        Resource = "arn:aws:events:${var.aws_region}:${var.aws_account_id}:rule/StepFunctionsGetEventsForBedrockModelInvocationJobsRule"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_permission" "list_manifests_sfn" {
  statement_id  = "AllowExecutionFromStepFunctions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.list_manifests.function_name
  principal     = "states.amazonaws.com"
  source_arn    = aws_sfn_state_machine.bulkrag_pipeline.arn
}

resource "aws_lambda_permission" "consolidate_chunks_sfn" {
  statement_id  = "AllowExecutionFromStepFunctions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.consolidate_chunks.function_name
  principal     = "states.amazonaws.com"
  source_arn    = aws_sfn_state_machine.bulkrag_pipeline.arn
}

resource "aws_lambda_permission" "run_bedrock_batch_sfn" {
  statement_id  = "AllowExecutionFromStepFunctions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.run_bedrock_batch.function_name
  principal     = "states.amazonaws.com"
  source_arn    = aws_sfn_state_machine.bulkrag_pipeline.arn
}

resource "aws_lambda_permission" "insert_pgvector_sfn" {
  statement_id  = "AllowExecutionFromStepFunctions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.insert_pgvector.function_name
  principal     = "states.amazonaws.com"
  source_arn    = aws_sfn_state_machine.bulkrag_pipeline.arn
}
