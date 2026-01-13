# SNS Topic for cost alerts
resource "aws_sns_topic" "cost_alerts" {
  name = "${local.prefix}-cost-alerts"
}

# SNS Topic subscription (email)
resource "aws_sns_topic_subscription" "cost_alerts_email" {
  topic_arn = aws_sns_topic.cost_alerts.arn
  protocol  = "email"
  endpoint  = var.cost_alert_email
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/${var.project_name}/${var.environment}"
  retention_in_days = 7 # Keep logs for 7 days to minimize costs
}

# Budget for overall spending
resource "aws_budgets_budget" "monthly" {
  name         = "${local.prefix}-monthly-budget"
  budget_type  = "COST"
  limit_amount = var.monthly_budget
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 25
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.cost_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.cost_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.cost_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 95
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.cost_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.cost_alert_email]
  }
}

# CloudWatch Alarm for Bedrock costs (daily)
resource "aws_cloudwatch_log_metric_filter" "bedrock_daily_spend" {
  name           = "${local.prefix}-bedrock-daily-spend"
  log_group_name = aws_cloudwatch_log_group.app.name
  pattern        = "[time, request_id, level, msg=\"Bedrock API call\", cost]"

  metric_transformation {
    name      = "BedrockDailySpend"
    namespace = "${var.project_name}/${var.environment}"
    value     = "$cost"
    unit      = "None"
  }
}

# CloudWatch Alarm for high Bedrock spending
resource "aws_cloudwatch_metric_alarm" "bedrock_daily_budget" {
  alarm_name          = "${local.prefix}-bedrock-daily-budget-exceeded"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BedrockDailySpend"
  namespace           = "${var.project_name}/${var.environment}"
  period              = "86400" # 24 hours
  statistic           = "Sum"
  threshold           = "1.50" # $1.50 daily budget
  alarm_description   = "Alert when Bedrock daily spending exceeds budget"
  alarm_actions       = [aws_sns_topic.cost_alerts.arn]
}

# CloudWatch Dashboard for cost monitoring
resource "aws_cloudwatch_dashboard" "cost_monitoring" {
  dashboard_name = "${local.prefix}-cost-monitoring"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", { stat = "Maximum" }]
          ]
          period = 86400
          stat   = "Maximum"
          region = "us-east-1"
          title  = "Estimated Monthly Charges"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["${var.project_name}/${var.environment}", "BedrockDailySpend", { stat = "Sum" }]
          ]
          period = 86400
          stat   = "Sum"
          region = local.region
          title  = "Bedrock Daily Spend"
        }
      }
    ]
  })
}
