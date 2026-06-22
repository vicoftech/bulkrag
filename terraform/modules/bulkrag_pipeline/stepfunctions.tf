resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/states/bulkrag-pipeline-${var.environment}"
  retention_in_days = 30
}

resource "aws_sfn_state_machine" "bulkrag_pipeline" {
  name     = "bulkrag-pipeline-${var.environment}"
  role_arn = aws_iam_role.step_functions_role.arn
  type     = "STANDARD"

  definition = templatefile("${path.module}/../../../step-functions/bulkrag-pipeline.asl.json", {
    ListManifestsLambdaArn     = aws_lambda_function.list_manifests.arn
    ConsolidateChunksLambdaArn = aws_lambda_function.consolidate_chunks.arn
    InsertPgvectorLambdaArn    = aws_lambda_function.insert_pgvector.arn
    RunBedrockBatchLambdaArn   = aws_lambda_function.run_bedrock_batch.arn
    EcsClusterArn              = var.ecs_cluster_arn
    EcsTaskDefinitionArn       = var.ecs_task_definition_arn
    EcsSubnetIds               = jsonencode(var.ecs_subnet_ids)
    EcsSecurityGroupId         = var.ecs_security_group_id
    BedrockBatchRoleArn        = var.bedrock_batch_role_arn
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  depends_on = [aws_iam_role_policy.step_functions_permissions]
}
