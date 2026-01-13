# Phase 1 Infrastructure - Core Database and Storage
# Estimated cost: ~$16/month

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  developer_ip       = var.developer_ip
  enable_nat_gateway = var.enable_nat_gateway
  tags               = var.tags
}

# RDS PostgreSQL Module
module "rds" {
  source = "./modules/rds"

  project_name       = var.project_name
  environment        = var.environment
  db_name            = "cti_scraper"
  db_username        = "cti_user"
  db_engine_version  = "16"  # Use latest 16.x version
  db_instance_class  = "db.t4g.micro"  # ARM-based for cost savings
  db_allocated_storage = 20

  # Network configuration
  db_subnet_group_name  = module.vpc.db_subnet_group_name
  rds_security_group_id = module.vpc.rds_security_group_id
  publicly_accessible   = true  # For Phase 1 dev access

  # Monitoring
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # Dev environment settings
  backup_retention_period = 7
  multi_az                = false
  deletion_protection     = false
  skip_final_snapshot     = true

  tags = var.tags

  depends_on = [module.vpc]
}

# S3 Module
module "s3" {
  source = "./modules/s3"

  project_name      = var.project_name
  environment       = var.environment
  enable_versioning = false  # Disabled for dev to save costs
  app_role_arn      = aws_iam_role.app_role.arn
  tags              = var.tags
}
