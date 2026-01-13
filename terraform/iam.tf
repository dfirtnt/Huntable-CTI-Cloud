# IAM role for Cost Explorer access
resource "aws_iam_role" "cost_monitor" {
  name = "${local.prefix}-cost-monitor-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "ecs-tasks.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
      }
    ]
  })
}

# Policy for Cost Explorer access
resource "aws_iam_policy" "cost_explorer" {
  name        = "${local.prefix}-cost-explorer-policy"
  description = "Policy for Cost Explorer access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetDimensionValues",
          "ce:GetTags"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach Cost Explorer policy to role
resource "aws_iam_role_policy_attachment" "cost_monitor_ce" {
  role       = aws_iam_role.cost_monitor.name
  policy_arn = aws_iam_policy.cost_explorer.arn
}

# Policy for CloudWatch Logs
resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "${local.prefix}-cloudwatch-logs-policy"
  description = "Policy for CloudWatch Logs access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/${var.project_name}/*"
      }
    ]
  })
}

# Attach CloudWatch Logs policy to role
resource "aws_iam_role_policy_attachment" "cost_monitor_logs" {
  role       = aws_iam_role.cost_monitor.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

# Policy for Bedrock access (for future phases)
resource "aws_iam_policy" "bedrock" {
  name        = "${local.prefix}-bedrock-policy"
  description = "Policy for AWS Bedrock access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "arn:aws:bedrock:${local.region}::foundation-model/*"
      }
    ]
  })
}

# IAM role for application (ECS/Lambda)
resource "aws_iam_role" "app_role" {
  name = "${local.prefix}-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "ecs-tasks.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
      }
    ]
  })
}

# Attach policies to app role
resource "aws_iam_role_policy_attachment" "app_role_ce" {
  role       = aws_iam_role.app_role.name
  policy_arn = aws_iam_policy.cost_explorer.arn
}

resource "aws_iam_role_policy_attachment" "app_role_logs" {
  role       = aws_iam_role.app_role.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

resource "aws_iam_role_policy_attachment" "app_role_bedrock" {
  role       = aws_iam_role.app_role.name
  policy_arn = aws_iam_policy.bedrock.arn
}

# ECS Task Execution Role (for pulling images, etc.)
resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.prefix}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM role for RDS Enhanced Monitoring
resource "aws_iam_role" "rds_monitoring" {
  name = "${local.prefix}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

# Attach AWS managed policy for RDS enhanced monitoring
resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
