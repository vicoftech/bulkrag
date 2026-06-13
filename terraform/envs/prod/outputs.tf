output "ecr_repository_url" {
  value = module.ecs_extractor.ecr_repository_url
}

output "ecs_cluster_arn" {
  value = module.ecs_extractor.ecs_cluster_arn
}

output "ecs_cluster_name" {
  value = module.ecs_extractor.ecs_cluster_name
}

output "task_definition_arn" {
  value = module.ecs_extractor.task_definition_arn
}

output "task_definition_family" {
  value = module.ecs_extractor.task_definition_family
}

output "security_group_id" {
  value = module.ecs_extractor.security_group_id
}

output "subnet_ids" {
  value = module.ecs_extractor.subnet_ids
}
