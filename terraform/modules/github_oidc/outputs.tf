output "role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "role_name" {
  value = aws_iam_role.github_actions.name
}

output "github_oidc_sub" {
  value = local.github_oidc_sub
}

output "oidc_provider_arn" {
  value = local.github_oidc_provider_arn
}
