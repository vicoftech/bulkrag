output "ecr_repository_url" {
  value = aws_ecr_repository.extractor.repository_url
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.extractor.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.extractor.name
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.extractor.arn
}

output "task_definition_family" {
  value = aws_ecs_task_definition.extractor.family
}

output "security_group_id" {
  value = aws_security_group.ecs_task.id
}

output "subnet_ids" {
  value = var.subnet_ids
}
