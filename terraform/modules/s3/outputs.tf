# S3 Module Outputs

output "content_bucket_id" {
  description = "ID of the content S3 bucket"
  value       = aws_s3_bucket.content.id
}

output "content_bucket_arn" {
  description = "ARN of the content S3 bucket"
  value       = aws_s3_bucket.content.arn
}

output "models_bucket_id" {
  description = "ID of the models S3 bucket"
  value       = aws_s3_bucket.models.id
}

output "models_bucket_arn" {
  description = "ARN of the models S3 bucket"
  value       = aws_s3_bucket.models.arn
}
