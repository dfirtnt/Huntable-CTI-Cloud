# Phase 2 Infrastructure - ML Pipeline
# Estimated cost: ~$4/month
#
# Components:
# - Lambda ML Trainer (3008MB, 15min timeout)
# - Lambda FastAPI Application (512MB)
# - API Gateway HTTP API
# - Security Groups and IAM Roles
# - CloudWatch Logs

# ============================================================================
# Lambda ML Trainer
# ============================================================================

# Upload ML trainer package to S3
resource "aws_s3_object" "ml_trainer_package" {
  count = var.deploy_ml_pipeline ? 1 : 0

  bucket = aws_s3_bucket.lambda_deployments.id
  key    = "ml-trainer/lambda_ml_trainer.zip"
  source = "${path.module}/../lambda_ml_trainer.zip"
  etag   = fileexists("${path.module}/../lambda_ml_trainer.zip") ? filemd5("${path.module}/../lambda_ml_trainer.zip") : null

  lifecycle {
    ignore_changes = [etag]
  }
}

# IAM role for ML trainer
resource "aws_iam_role" "lambda_ml_trainer" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name = "${var.project_name}-${var.environment}-lambda-ml-trainer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

# Attach basic execution policy
resource "aws_iam_role_policy_attachment" "ml_trainer_basic" {
  count      = var.deploy_ml_pipeline ? 1 : 0
  role       = aws_iam_role.lambda_ml_trainer[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Attach VPC execution policy
resource "aws_iam_role_policy_attachment" "ml_trainer_vpc" {
  count      = var.deploy_ml_pipeline ? 1 : 0
  role       = aws_iam_role.lambda_ml_trainer[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Custom policy for RDS and S3
resource "aws_iam_role_policy" "ml_trainer_custom" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name = "${var.project_name}-${var.environment}-ml-trainer-policy"
  role = aws_iam_role.lambda_ml_trainer[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [module.rds.db_password_secret_arn]
      },
      {
        Sid    = "S3ModelAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
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

# Security group for ML trainer Lambda
resource "aws_security_group" "lambda_ml_trainer" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name        = "${var.project_name}-${var.environment}-lambda-ml-trainer-sg"
  description = "Security group for ML trainer Lambda"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.vpc.rds_security_group_id]
    description     = "PostgreSQL to RDS"
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS for S3 access"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-ml-trainer-sg"
    }
  )
}

# Allow ML trainer to access RDS
resource "aws_security_group_rule" "rds_from_ml_trainer" {
  count = var.deploy_ml_pipeline ? 1 : 0

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.vpc.rds_security_group_id
  source_security_group_id = aws_security_group.lambda_ml_trainer[0].id
  description              = "PostgreSQL from ML trainer Lambda"
}

# Lambda function for ML training
# Temporarily disabled due to package size issue (250MB unzipped limit exceeded)
resource "aws_lambda_function" "ml_trainer" {
  count = 0 # var.deploy_ml_pipeline ? 1 : 0

  function_name = "${var.project_name}-${var.environment}-ml-trainer"
  description   = "ML model training for content classification"

  s3_bucket        = aws_s3_bucket.lambda_deployments.id
  s3_key           = aws_s3_object.ml_trainer_package[0].key
  source_code_hash = fileexists("${path.module}/../lambda_ml_trainer.zip") ? filebase64sha256("${path.module}/../lambda_ml_trainer.zip") : ""

  handler = "cti_scraper.lambda_ml_trainer.handler"
  runtime = "python3.11"

  role = aws_iam_role.lambda_ml_trainer[0].arn

  # High memory for faster training (max CPU allocation)
  timeout     = 900  # 15 minutes
  memory_size = 3008 # Maximum

  # Ephemeral storage for model artifacts
  ephemeral_storage {
    size = 10240 # 10 GB
  }

  # VPC config for RDS access
  vpc_config {
    subnet_ids         = module.vpc.public_subnet_ids
    security_group_ids = [aws_security_group.lambda_ml_trainer[0].id]
  }

  environment {
    variables = {
      APP_ENV              = var.environment
      LOG_LEVEL            = "INFO"
      DATABASE_SECRET_ID   = module.rds.db_password_secret_id
      AWS_REGION_NAME      = var.aws_region
      ML_MODEL_BUCKET      = module.s3.models_bucket_id
      ML_MODEL_KEY         = "models/content_filter/model.pkl"
      ML_VECTORIZER_KEY    = "models/content_filter/vectorizer.pkl"
      ML_METADATA_KEY      = "models/content_filter/metadata.json"
      MIN_TRAINING_SAMPLES = "10"
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.ml_trainer_basic,
    aws_iam_role_policy_attachment.ml_trainer_vpc,
    aws_iam_role_policy.ml_trainer_custom
  ]
}

# CloudWatch Log Group for ML trainer
resource "aws_cloudwatch_log_group" "ml_trainer" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name              = "/aws/lambda/${var.project_name}-${var.environment}-ml-trainer"
  retention_in_days = 14

  tags = var.tags
}

# ============================================================================
# Lambda FastAPI Application
# ============================================================================

# Upload API package to S3
resource "aws_s3_object" "api_package" {
  count = var.deploy_ml_pipeline ? 1 : 0

  bucket = aws_s3_bucket.lambda_deployments.id
  key    = "api/lambda_api.zip"
  source = "${path.module}/../lambda_api.zip"
  etag   = fileexists("${path.module}/../lambda_api.zip") ? filemd5("${path.module}/../lambda_api.zip") : null

  lifecycle {
    ignore_changes = [etag]
  }
}

# IAM role for API Lambda
resource "aws_iam_role" "lambda_api" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name = "${var.project_name}-${var.environment}-lambda-api"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

# Attach basic execution policy
resource "aws_iam_role_policy_attachment" "api_basic" {
  count      = var.deploy_ml_pipeline ? 1 : 0
  role       = aws_iam_role.lambda_api[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Attach VPC execution policy
resource "aws_iam_role_policy_attachment" "api_vpc" {
  count      = var.deploy_ml_pipeline ? 1 : 0
  role       = aws_iam_role.lambda_api[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Custom policy for RDS, S3, and Lambda invocation
resource "aws_iam_role_policy" "api_custom" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name = "${var.project_name}-${var.environment}-api-policy"
  role = aws_iam_role.lambda_api[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [module.rds.db_password_secret_arn]
      },
      {
        Sid    = "S3ModelAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          module.s3.models_bucket_arn,
          "${module.s3.models_bucket_arn}/*"
        ]
      },
      # ML Trainer invocation - disabled until package size issue is resolved
      #{
      #  Sid    = "InvokeMLTrainer"
      #  Effect = "Allow"
      #  Action = ["lambda:InvokeFunction"]
      #  Resource = var.deploy_ml_pipeline ? [aws_lambda_function.ml_trainer[0].arn] : []
      #}
    ]
  })
}

# Security group for API Lambda
resource "aws_security_group" "lambda_api" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name        = "${var.project_name}-${var.environment}-lambda-api-sg"
  description = "Security group for API Lambda"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.vpc.rds_security_group_id]
    description     = "PostgreSQL to RDS"
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS for AWS services"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-api-sg"
    }
  )
}

# Allow API Lambda to access RDS
resource "aws_security_group_rule" "rds_from_api" {
  count = var.deploy_ml_pipeline ? 1 : 0

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.vpc.rds_security_group_id
  source_security_group_id = aws_security_group.lambda_api[0].id
  description              = "PostgreSQL from API Lambda"
}

# Lambda function for FastAPI app
resource "aws_lambda_function" "api" {
  count = var.deploy_ml_pipeline ? 1 : 0

  function_name = "${var.project_name}-${var.environment}-api"
  description   = "FastAPI application for CTI Scraper"

  s3_bucket        = aws_s3_bucket.lambda_deployments.id
  s3_key           = aws_s3_object.api_package[0].key
  source_code_hash = fileexists("${path.module}/../lambda_api.zip") ? filebase64sha256("${path.module}/../lambda_api.zip") : ""

  handler = "cti_scraper.lambda_api.handler"
  runtime = "python3.11"

  role = aws_iam_role.lambda_api[0].arn

  timeout     = 30  # API responses should be fast
  memory_size = 512

  vpc_config {
    subnet_ids         = module.vpc.public_subnet_ids
    security_group_ids = [aws_security_group.lambda_api[0].id]
  }

  environment {
    variables = {
      APP_ENV                  = var.environment
      LOG_LEVEL                = "INFO"
      DATABASE_SECRET_ID       = module.rds.db_password_secret_id
      AWS_REGION_NAME          = var.aws_region
      ML_MODEL_BUCKET          = module.s3.models_bucket_id
      ML_TRAINER_FUNCTION_NAME = "" # Disabled until package size issue is resolved
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.api_basic,
    aws_iam_role_policy_attachment.api_vpc,
    aws_iam_role_policy.api_custom
  ]
}

# CloudWatch Log Group for API Lambda
resource "aws_cloudwatch_log_group" "api" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name              = "/aws/lambda/${var.project_name}-${var.environment}-api"
  retention_in_days = 14

  tags = var.tags
}

# ============================================================================
# API Gateway HTTP API
# ============================================================================

# API Gateway HTTP API (simpler, cheaper than REST API)
resource "aws_apigatewayv2_api" "main" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name          = "${var.project_name}-${var.environment}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["*"]
  }

  tags = var.tags
}

# API Gateway stage
resource "aws_apigatewayv2_stage" "default" {
  count = var.deploy_ml_pipeline ? 1 : 0

  api_id      = aws_apigatewayv2_api.main[0].id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway[0].arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = var.tags
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  count = var.deploy_ml_pipeline ? 1 : 0

  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = 7

  tags = var.tags
}

# Integration with Lambda
resource "aws_apigatewayv2_integration" "lambda_api" {
  count = var.deploy_ml_pipeline ? 1 : 0

  api_id           = aws_apigatewayv2_api.main[0].id
  integration_type = "AWS_PROXY"

  integration_uri        = aws_lambda_function.api[0].invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# Catch-all route (FastAPI handles routing internally)
resource "aws_apigatewayv2_route" "default" {
  count = var.deploy_ml_pipeline ? 1 : 0

  api_id    = aws_apigatewayv2_api.main[0].id
  route_key = "$default"

  target = "integrations/${aws_apigatewayv2_integration.lambda_api[0].id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  count = var.deploy_ml_pipeline ? 1 : 0

  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api[0].function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.main[0].execution_arn}/*/*"
}

# ============================================================================
# Outputs
# ============================================================================

output "ml_trainer_function_name" {
  description = "ML trainer Lambda function name"
  value       = null # Disabled until package size issue is resolved
}

output "ml_trainer_function_arn" {
  description = "ML trainer Lambda function ARN"
  value       = null # Disabled until package size issue is resolved
}

output "api_function_name" {
  description = "API Lambda function name"
  value       = var.deploy_ml_pipeline ? aws_lambda_function.api[0].function_name : null
}

output "api_function_arn" {
  description = "API Lambda function ARN"
  value       = var.deploy_ml_pipeline ? aws_lambda_function.api[0].arn : null
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = var.deploy_ml_pipeline ? aws_apigatewayv2_stage.default[0].invoke_url : null
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = var.deploy_ml_pipeline ? aws_apigatewayv2_api.main[0].id : null
}
