variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "cti-scraper"
}

variable "environment" {
  description = "Environment (dev, prod)"
  type        = string
  default     = "dev"
}

variable "cost_alert_email" {
  description = "Email address for cost alerts"
  type        = string
}

variable "cost_alert_threshold_25" {
  description = "25% budget threshold in USD"
  type        = number
  default     = 25.00
}

variable "cost_alert_threshold_50" {
  description = "50% budget threshold in USD"
  type        = number
  default     = 50.00
}

variable "cost_alert_threshold_80" {
  description = "80% budget threshold in USD"
  type        = number
  default     = 80.00
}

variable "cost_alert_threshold_95" {
  description = "95% budget threshold in USD"
  type        = number
  default     = 95.00
}

variable "monthly_budget" {
  description = "Total monthly budget in USD"
  type        = number
  default     = 100.00
}

variable "developer_ip" {
  description = "Developer IP address for RDS access (CIDR format, e.g., '1.2.3.4/32'). Set to empty string to disable."
  type        = string
  default     = ""
}

variable "deploy_lambda" {
  description = "Deploy Lambda function (requires lambda_package.zip to exist)"
  type        = bool
  default     = false
}

variable "deploy_ml_pipeline" {
  description = "Deploy ML trainer Lambda (Phase 2)"
  type        = bool
  default     = false
}

variable "deploy_api" {
  description = "Deploy API Lambda and API Gateway (web UI)"
  type        = bool
  default     = false
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for Lambda internet access (+$32/month). Required for Lambda to scrape external RSS feeds."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project   = "cti-scraper"
    ManagedBy = "terraform"
  }
}
