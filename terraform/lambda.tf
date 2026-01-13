# Lambda + EventBridge for CTI Scraper
# Estimated cost: ~$0-2/month (within free tier for typical usage)
# Set deploy_lambda = true after creating lambda_package.zip

# Lambda execution role
resource "aws_iam_role" "lambda_scraper" {
  count = var.deploy_lambda ? 1 : 0

  name = "${var.project_name}-${var.environment}-lambda-scraper"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Lambda basic execution policy (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  count = var.deploy_lambda ? 1 : 0

  role       = aws_iam_role.lambda_scraper[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda VPC access policy (for RDS access)
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  count = var.deploy_lambda ? 1 : 0

  role       = aws_iam_role.lambda_scraper[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Custom policy for Secrets Manager (RDS password)
resource "aws_iam_role_policy" "lambda_secrets" {
  count = var.deploy_lambda ? 1 : 0

  name = "${var.project_name}-${var.environment}-lambda-secrets"
  role = aws_iam_role.lambda_scraper[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          module.rds.db_password_secret_arn
        ]
      }
    ]
  })
}

# Custom policy for S3 access (content + ML models)
resource "aws_iam_role_policy" "lambda_s3" {
  count = var.deploy_lambda ? 1 : 0

  name = "${var.project_name}-${var.environment}-lambda-s3"
  role = aws_iam_role.lambda_scraper[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ContentBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          module.s3.content_bucket_arn,
          "${module.s3.content_bucket_arn}/*"
        ]
      },
      {
        Sid    = "MLModelsBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          module.s3.models_bucket_arn,
          "${module.s3.models_bucket_arn}/*"
        ]
      }
    ]
  })
}

# Security group for Lambda (outbound internet + RDS access)
resource "aws_security_group" "lambda_scraper" {
  count = var.deploy_lambda ? 1 : 0

  name        = "${var.project_name}-${var.environment}-lambda-sg"
  description = "Security group for Lambda scraper"
  vpc_id      = module.vpc.vpc_id

  # HTTPS outbound (for scraping)
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS outbound for scraping"
  }

  # HTTP outbound (for scraping)
  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP outbound for scraping"
  }

  # PostgreSQL to RDS
  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.vpc.rds_security_group_id]
    description     = "PostgreSQL to RDS"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-sg"
    }
  )
}

# Allow Lambda security group to access RDS
resource "aws_security_group_rule" "rds_from_lambda" {
  count = var.deploy_lambda ? 1 : 0

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.vpc.rds_security_group_id
  source_security_group_id = aws_security_group.lambda_scraper[0].id
  description              = "PostgreSQL from Lambda"
}

# S3 bucket for Lambda deployment packages (always created)
resource "aws_s3_bucket" "lambda_deployments" {
  bucket_prefix = "${var.project_name}-${var.environment}-lambda-"

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-lambda-deployments"
      Purpose = "Lambda deployment packages"
    }
  )
}

resource "aws_s3_bucket_versioning" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Local to safely compute file hash only when file exists
locals {
  lambda_package_path   = "${path.module}/../lambda_package.zip"
  lambda_package_exists = fileexists(local.lambda_package_path)
  lambda_package_hash   = local.lambda_package_exists ? filebase64sha256(local.lambda_package_path) : ""
}

# Upload Lambda package to S3
# Run `python scripts/build_lambda.py` before setting deploy_lambda = true
resource "aws_s3_object" "lambda_package" {
  count = var.deploy_lambda && local.lambda_package_exists ? 1 : 0

  bucket = aws_s3_bucket.lambda_deployments.id
  key    = "scraper/lambda_package.zip"
  source = local.lambda_package_path
  etag   = local.lambda_package_hash
}

# Data source to fetch database credentials from Secrets Manager
data "aws_secretsmanager_secret_version" "db_password" {
  count = var.deploy_lambda ? 1 : 0

  secret_id = module.rds.db_password_secret_id
}

# Local to build DATABASE_URL from secret
locals {
  db_credentials = var.deploy_lambda ? jsondecode(data.aws_secretsmanager_secret_version.db_password[0].secret_string) : {}
  database_url   = var.deploy_lambda ? "postgresql+asyncpg://${local.db_credentials.username}:${urlencode(local.db_credentials.password)}@${local.db_credentials.host}:${local.db_credentials.port}/${local.db_credentials.dbname}" : ""
}

# Lambda function
resource "aws_lambda_function" "scraper" {
  count = var.deploy_lambda ? 1 : 0

  function_name = "${var.project_name}-${var.environment}-scraper"
  description   = "CTI Scraper - Threat Intelligence Collection"

  # Deploy from S3
  s3_bucket        = aws_s3_bucket.lambda_deployments.id
  s3_key           = aws_s3_object.lambda_package[0].key
  source_code_hash = local.lambda_package_hash

  handler = "cti_scraper.lambda_handler.handler"
  runtime = "python3.11"

  role = aws_iam_role.lambda_scraper[0].arn

  # Timeout: 10 minutes (RSS scraping can take a while)
  timeout     = 600
  memory_size = 512

  # VPC config for secure RDS access
  # Use private subnets if NAT Gateway is enabled, otherwise use public subnets
  vpc_config {
    subnet_ids         = module.vpc.has_nat_gateway ? module.vpc.private_subnet_ids : module.vpc.public_subnet_ids
    security_group_ids = [aws_security_group.lambda_scraper[0].id]
  }

  environment {
    variables = {
      APP_ENV           = var.environment
      LOG_LEVEL         = "INFO"
      DATABASE_URL      = local.database_url
      AWS_REGION_NAME   = var.aws_region
      # ML Model configuration
      ML_MODEL_BUCKET   = module.s3.models_bucket_id
      ML_MODEL_KEY      = "models/content_filter/model.pkl"
      ML_VECTORIZER_KEY = "models/content_filter/vectorizer.pkl"
      ML_MODEL_VERSION  = "latest"
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_vpc,
  ]
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_scraper" {
  count = var.deploy_lambda ? 1 : 0

  name              = "/aws/lambda/${var.project_name}-${var.environment}-scraper"
  retention_in_days = 14

  tags = var.tags
}

# EventBridge rule - Run every hour
resource "aws_cloudwatch_event_rule" "scraper_schedule" {
  count = var.deploy_lambda ? 1 : 0

  name                = "${var.project_name}-${var.environment}-scraper-schedule"
  description         = "Trigger CTI scraper every hour"
  schedule_expression = "rate(1 hour)"

  tags = var.tags
}

# EventBridge target - Lambda
resource "aws_cloudwatch_event_target" "scraper_lambda" {
  count = var.deploy_lambda ? 1 : 0

  rule      = aws_cloudwatch_event_rule.scraper_schedule[0].name
  target_id = "ScraperLambda"
  arn       = aws_lambda_function.scraper[0].arn
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "eventbridge" {
  count = var.deploy_lambda ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scraper[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scraper_schedule[0].arn
}

# Outputs
output "lambda_function_name" {
  description = "Lambda function name"
  value       = var.deploy_lambda ? aws_lambda_function.scraper[0].function_name : null
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = var.deploy_lambda ? aws_lambda_function.scraper[0].arn : null
}

output "lambda_log_group" {
  description = "CloudWatch log group for Lambda"
  value       = var.deploy_lambda ? aws_cloudwatch_log_group.lambda_scraper[0].name : null
}

output "eventbridge_rule" {
  description = "EventBridge schedule rule name"
  value       = var.deploy_lambda ? aws_cloudwatch_event_rule.scraper_schedule[0].name : null
}

output "lambda_deployment_bucket" {
  description = "S3 bucket for Lambda deployments"
  value       = aws_s3_bucket.lambda_deployments.id
}
