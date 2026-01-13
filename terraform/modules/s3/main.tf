# S3 Module - Content storage and ML models
# Minimal cost - only pay for what you store

terraform {
  required_version = ">= 1.5.0"
}

# S3 Bucket for raw content storage
resource "aws_s3_bucket" "content" {
  bucket_prefix = "${var.project_name}-${var.environment}-content-"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-content"
      Purpose = "Raw article content and attachments"
    }
  )
}

# Enable versioning (for content recovery)
resource "aws_s3_bucket_versioning" "content" {
  bucket = aws_s3_bucket.content.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "content" {
  bucket = aws_s3_bucket.content.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle policy to manage costs
resource "aws_s3_bucket_lifecycle_configuration" "content" {
  bucket = aws_s3_bucket.content.id

  # Transition old content to cheaper storage classes
  rule {
    id     = "transition-old-content"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER_IR"
    }
  }

  # Clean up old versions
  rule {
    id     = "expire-old-versions"
    status = var.enable_versioning ? "Enabled" : "Disabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  # Clean up incomplete multipart uploads
  rule {
    id     = "cleanup-multipart-uploads"
    status = "Enabled"

    filter {
      prefix = ""
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "content" {
  bucket = aws_s3_bucket.content.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket for ML models (Phase 2+)
resource "aws_s3_bucket" "models" {
  bucket_prefix = "${var.project_name}-${var.environment}-models-"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-models"
      Purpose = "ML models and embeddings"
    }
  )
}

# Enable versioning for models (track model versions)
resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption for models
resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access for models
resource "aws_s3_bucket_public_access_block" "models" {
  bucket = aws_s3_bucket.models.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket policy for content bucket (allow access from app role)
resource "aws_s3_bucket_policy" "content" {
  count  = var.app_role_arn != "" ? 1 : 0
  bucket = aws_s3_bucket.content.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAppRoleAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.app_role_arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.content.arn,
          "${aws_s3_bucket.content.arn}/*"
        ]
      }
    ]
  })
}

# Bucket policy for models bucket
resource "aws_s3_bucket_policy" "models" {
  count  = var.app_role_arn != "" ? 1 : 0
  bucket = aws_s3_bucket.models.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAppRoleAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.app_role_arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.models.arn,
          "${aws_s3_bucket.models.arn}/*"
        ]
      }
    ]
  })
}
