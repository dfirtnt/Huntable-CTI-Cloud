output "account_id" {
  description = "AWS Account ID"
  value       = local.account_id
}

output "region" {
  description = "AWS Region"
  value       = local.region
}

output "cost_monitor_role_arn" {
  description = "ARN of the cost monitor IAM role"
  value       = aws_iam_role.cost_monitor.arn
}

output "app_role_arn" {
  description = "ARN of the application IAM role"
  value       = aws_iam_role.app_role.arn
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "cost_alerts_topic_arn" {
  description = "ARN of the cost alerts SNS topic"
  value       = aws_sns_topic.cost_alerts.arn
}

output "log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.app.name
}

output "budget_name" {
  description = "Name of the AWS budget"
  value       = aws_budgets_budget.monthly.name
}

output "dashboard_url" {
  description = "URL to CloudWatch dashboard"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${local.region}#dashboards:name=${aws_cloudwatch_dashboard.cost_monitoring.dashboard_name}"
}

# Phase 1 Outputs

output "vpc_id" {
  description = "ID of the VPC"
  value       = try(module.vpc.vpc_id, null)
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = try(module.rds.db_instance_endpoint, null)
}

output "rds_password_secret_arn" {
  description = "ARN of RDS password in Secrets Manager"
  value       = try(module.rds.db_password_secret_arn, null)
  sensitive   = true
}

output "content_bucket_name" {
  description = "Name of the content S3 bucket"
  value       = try(module.s3.content_bucket_id, null)
}

output "models_bucket_name" {
  description = "Name of the models S3 bucket"
  value       = try(module.s3.models_bucket_id, null)
}

output "rds_connection_string" {
  description = "PostgreSQL connection string (retrieve password from Secrets Manager)"
  value       = try(module.rds.db_connection_string, null)
  sensitive   = true
}
