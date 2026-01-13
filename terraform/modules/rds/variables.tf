# RDS Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "db_name" {
  description = "Name of the database"
  type        = string
  default     = "cti_scraper"
}

variable "db_username" {
  description = "Master username for database"
  type        = string
  default     = "cti_user"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16.1"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_subnet_group_name" {
  description = "Name of DB subnet group"
  type        = string
}

variable "rds_security_group_id" {
  description = "ID of RDS security group"
  type        = string
}

variable "publicly_accessible" {
  description = "Whether database is publicly accessible"
  type        = bool
  default     = true  # For Phase 1 dev access; change to false for production
}

variable "backup_retention_period" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

variable "multi_az" {
  description = "Enable Multi-AZ deployment"
  type        = bool
  default     = false  # Disabled for dev to save costs
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = false  # Disabled for dev environment
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on deletion"
  type        = bool
  default     = true  # True for dev environment
}

variable "monitoring_role_arn" {
  description = "ARN of IAM role for enhanced monitoring"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default     = {}
}
