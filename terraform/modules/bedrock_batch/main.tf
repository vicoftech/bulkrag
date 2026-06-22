resource "aws_iam_role" "bedrock_batch" {
  name = "bulkrag-bedrock-batch-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "bedrock.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = var.aws_account_id
        }
        ArnLike = {
          "aws:SourceArn" = "arn:aws:bedrock:${var.aws_region}:${var.aws_account_id}:model-invocation-job/*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_batch_s3" {
  name = "bulkrag-bedrock-batch-s3"
  role = aws_iam_role.bedrock_batch.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          "arn:aws:s3:::${var.rag_bucket_name}",
          "arn:aws:s3:::${var.rag_bucket_name}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_embed_model_id}",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.embed-multilingual-v3",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.embed-english-v3"
        ]
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
