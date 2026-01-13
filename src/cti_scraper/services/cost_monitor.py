"""AWS Cost Monitoring Service"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from cti_scraper.config import get_settings

logger = logging.getLogger(__name__)


class CostMonitorService:
    """Service for monitoring AWS costs and usage"""

    def __init__(self):
        self.settings = get_settings()
        # Only pass credentials if explicitly set, otherwise use AWS SSO/default credentials
        client_kwargs = {"region_name": self.settings.aws_region}
        if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
        self.ce_client = boto3.client("ce", **client_kwargs)

    def get_month_to_date_cost(self) -> Dict[str, float]:
        """Get month-to-date costs"""
        try:
            # Get first day of current month
            today = datetime.utcnow().date()
            start_date = today.replace(day=1).isoformat()
            end_date = today.isoformat()

            response = self.ce_client.get_cost_and_usage(
                TimePeriod={"Start": start_date, "End": end_date},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )

            if response["ResultsByTime"]:
                amount = float(response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
                return {
                    "amount": amount,
                    "start_date": start_date,
                    "end_date": end_date,
                    "currency": "USD",
                }

            return {"amount": 0.0, "start_date": start_date, "end_date": end_date, "currency": "USD"}

        except ClientError as e:
            logger.error(f"Error fetching month-to-date cost: {e}")
            return {"amount": 0.0, "error": str(e)}

    def get_daily_costs(self, days: int = 7) -> List[Dict[str, any]]:
        """Get daily costs for the last N days"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            response = self.ce_client.get_cost_and_usage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
            )

            daily_costs = []
            for result in response["ResultsByTime"]:
                daily_costs.append({
                    "date": result["TimePeriod"]["Start"],
                    "amount": float(result["Total"]["UnblendedCost"]["Amount"]),
                    "currency": "USD",
                })

            return daily_costs

        except ClientError as e:
            logger.error(f"Error fetching daily costs: {e}")
            return []

    def get_cost_by_service(self, days: int = 30) -> Dict[str, float]:
        """Get costs grouped by AWS service for the last N days"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            response = self.ce_client.get_cost_and_usage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            service_costs = {}
            if response["ResultsByTime"]:
                for group in response["ResultsByTime"][0]["Groups"]:
                    service_name = group["Keys"][0]
                    amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    if amount > 0.01:  # Filter out negligible costs
                        service_costs[service_name] = amount

            return service_costs

        except ClientError as e:
            logger.error(f"Error fetching cost by service: {e}")
            return {}

    def get_bedrock_costs(self) -> Dict[str, any]:
        """Get Bedrock-specific costs and usage"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date.replace(day=1)  # Start of month

            # Get Bedrock costs
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                Filter={
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": ["Amazon Bedrock"],
                    }
                },
            )

            bedrock_cost = 0.0
            if response["ResultsByTime"]:
                bedrock_cost = float(response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])

            return {
                "total_cost": bedrock_cost,
                "daily_budget": self.settings.bedrock_daily_budget,
                "monthly_budget": self.settings.bedrock_monthly_budget,
                "budget_used_percent": (bedrock_cost / self.settings.bedrock_monthly_budget) * 100 if self.settings.bedrock_monthly_budget > 0 else 0,
            }

        except ClientError as e:
            logger.error(f"Error fetching Bedrock costs: {e}")
            return {"total_cost": 0.0, "error": str(e)}

    def get_projected_cost(self) -> Dict[str, float]:
        """Project end-of-month cost based on current daily average"""
        try:
            mtd_data = self.get_month_to_date_cost()
            mtd_amount = mtd_data.get("amount", 0.0)

            today = datetime.utcnow().date()
            days_elapsed = today.day
            days_in_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            total_days = days_in_month.day

            if days_elapsed > 0:
                daily_average = mtd_amount / days_elapsed
                projected_eom = daily_average * total_days
            else:
                daily_average = 0.0
                projected_eom = 0.0

            return {
                "month_to_date": mtd_amount,
                "daily_average": daily_average,
                "projected_eom": projected_eom,
                "days_elapsed": days_elapsed,
                "total_days": total_days,
            }

        except Exception as e:
            logger.error(f"Error calculating projected cost: {e}")
            return {"month_to_date": 0.0, "daily_average": 0.0, "projected_eom": 0.0}

    def check_budget_alerts(self) -> List[Dict[str, any]]:
        """Check if any budget thresholds have been exceeded"""
        alerts = []
        mtd_data = self.get_month_to_date_cost()
        mtd_amount = mtd_data.get("amount", 0.0)

        thresholds = [
            (self.settings.cost_alert_threshold_25, "INFO", "25% budget threshold reached"),
            (self.settings.cost_alert_threshold_50, "WARNING", "50% budget threshold reached"),
            (self.settings.cost_alert_threshold_80, "CRITICAL", "80% budget threshold reached"),
            (self.settings.cost_alert_threshold_95, "EMERGENCY", "95% budget threshold - IMMEDIATE ACTION REQUIRED"),
        ]

        for threshold, severity, message in thresholds:
            if mtd_amount >= threshold:
                alerts.append({
                    "threshold": threshold,
                    "current": mtd_amount,
                    "severity": severity,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return alerts

    def get_cost_summary(self) -> Dict[str, any]:
        """Get comprehensive cost summary"""
        try:
            mtd_data = self.get_month_to_date_cost()
            projected = self.get_projected_cost()
            by_service = self.get_cost_by_service()
            bedrock = self.get_bedrock_costs()
            alerts = self.check_budget_alerts()

            return {
                "month_to_date": mtd_data,
                "projected": projected,
                "by_service": by_service,
                "bedrock": bedrock,
                "alerts": alerts,
                "budget": {
                    "total_monthly": 100.0,
                    "used_percent": (mtd_data.get("amount", 0.0) / 100.0) * 100,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating cost summary: {e}")
            return {"error": str(e)}

    def get_bedrock_daily_spend(self) -> float:
        """Get today's Bedrock spending"""
        try:
            today = datetime.utcnow().date()
            tomorrow = today + timedelta(days=1)

            response = self.ce_client.get_cost_and_usage(
                TimePeriod={"Start": today.isoformat(), "End": tomorrow.isoformat()},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
                Filter={
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": ["Amazon Bedrock"],
                    }
                },
            )

            if response["ResultsByTime"]:
                return float(response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])

            return 0.0

        except ClientError as e:
            logger.error(f"Error fetching Bedrock daily spend: {e}")
            return 0.0

    def check_bedrock_daily_budget(self) -> bool:
        """Check if Bedrock daily budget has been exceeded"""
        daily_spend = self.get_bedrock_daily_spend()
        return daily_spend < self.settings.bedrock_daily_budget
