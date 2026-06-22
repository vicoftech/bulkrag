resource "aws_secretsmanager_secret" "aurora" {
  count = local.create_secret ? 1 : 0
  name  = "bulkrag/aurora/${var.environment}"
}

resource "aws_secretsmanager_secret_version" "aurora" {
  count     = local.create_secret ? 1 : 0
  secret_id = aws_secretsmanager_secret.aurora[0].id
  secret_string = jsonencode({
    host     = var.aurora_host
    port     = 5432
    username = var.aurora_db_user
    password = var.aurora_db_password
    dbname   = var.aurora_db_name
  })
}

resource "aws_security_group" "insert_pgvector_lambda" {
  count       = local.aurora_enabled ? 1 : 0
  name        = "bulkrag-insert-pgvector-lambda-${var.environment}"
  description = "Lambda insert_pgvector to Aurora"
  vpc_id      = var.aurora_vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "aurora_from_lambda" {
  count                    = local.aurora_enabled ? 1 : 0
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = var.aurora_security_group_id
  source_security_group_id = aws_security_group.insert_pgvector_lambda[0].id
  description              = "bulkrag insert_pgvector lambda"
}

resource "aws_security_group_rule" "secrets_vpce_from_lambda" {
  count                    = local.aurora_enabled && var.aurora_vpce_security_group_id != "" ? 1 : 0
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = var.aurora_vpce_security_group_id
  source_security_group_id = aws_security_group.insert_pgvector_lambda[0].id
  description              = "bulkrag insert_pgvector lambda"
}
