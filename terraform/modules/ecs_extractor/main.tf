# ── ECR ──────────────────────────────────────────────────────────────────────
resource "aws_ecr_repository" "extractor" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "extractor" {
  repository = aws_ecr_repository.extractor.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retener solo las últimas 5 imágenes"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# ── ECS Cluster ──────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "extractor" {
  name = "rag-extractor-poc-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ── IAM Role para la Task ─────────────────────────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name = "rag-ecs-extractor-execution-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "rag-ecs-extractor-task-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "rag-ecs-extractor-s3-policy"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.rag_bucket_name}",
          "arn:aws:s3:::${var.rag_bucket_name}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "extractor" {
  name              = "/ecs/rag-extractor-poc-${var.environment}"
  retention_in_days = 7
}

# ── Task Definition ───────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "extractor" {
  family                   = "rag-extractor-poc-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "extractor"
    image     = "${aws_ecr_repository.extractor.repository_url}:latest"
    essential = true
    environment = [
      { name = "RAG_BUCKET_NAME", value = var.rag_bucket_name },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "WORKER_COUNT", value = tostring(var.worker_count) },
      { name = "MAX_FILE_SIZE_MB", value = tostring(var.max_file_size_mb) },
      { name = "CHUNK_SIZE_TOKENS", value = tostring(var.chunk_size_tokens) },
      { name = "CHUNK_OVERLAP_TOKENS", value = tostring(var.chunk_overlap_tokens) },
      { name = "BEDROCK_EMBED_MODEL_ID", value = var.bedrock_embed_model_id },
      { name = "EMBED_DIMENSIONS", value = tostring(var.embed_dimensions) },
      { name = "EMBED_MAX_CHARS", value = tostring(var.embed_max_chars) }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.extractor.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
}

# ── Security Group para la Task ───────────────────────────────────────────────
resource "aws_security_group" "ecs_task" {
  name        = "rag-ecs-extractor-sg-${var.environment}"
  description = "ECS extractor POC - egress only"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
