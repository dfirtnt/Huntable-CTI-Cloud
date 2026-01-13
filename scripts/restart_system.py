#!/usr/bin/env python3
"""
Restart System Script

This script restarts CTI Scraper resources after an emergency shutdown.

Usage:
    python scripts/restart_system.py [--dry-run]

Options:
    --dry-run: Show what would be done without actually doing it
"""
import argparse
import logging
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cti_scraper.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SystemRestart:
    """Handle system restart after emergency shutdown"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.settings = get_settings()
        self.ecs_client = boto3.client("ecs", region_name=self.settings.aws_region)
        self.lambda_client = boto3.client("lambda", region_name=self.settings.aws_region)
        self.events_client = boto3.client("events", region_name=self.settings.aws_region)
        self.rds_client = boto3.client("rds", region_name=self.settings.aws_region)

    def log_action(self, action: str, details: str = ""):
        """Log action with dry-run indicator"""
        prefix = "[DRY-RUN] " if self.dry_run else ""
        logger.info(f"{prefix}{action}: {details}")

    def enable_eventbridge_rules(self) -> int:
        """Enable all EventBridge rules for the project"""
        try:
            self.log_action("Checking EventBridge rules")
            response = self.events_client.list_rules(NamePrefix=f"{self.settings.app_env}-")

            enabled_count = 0
            for rule in response.get("Rules", []):
                rule_name = rule["Name"]
                if rule["State"] == "DISABLED":
                    if not self.dry_run:
                        self.events_client.enable_rule(Name=rule_name)
                    self.log_action(f"Enabled EventBridge rule", rule_name)
                    enabled_count += 1

            return enabled_count

        except ClientError as e:
            logger.error(f"Error enabling EventBridge rules: {e}")
            return 0

    def enable_lambda_event_sources(self) -> int:
        """Enable Lambda event source mappings"""
        try:
            self.log_action("Checking Lambda event sources")

            # List all Lambda functions
            functions_response = self.lambda_client.list_functions()
            enabled_count = 0

            for function in functions_response.get("Functions", []):
                function_name = function["FunctionName"]

                # Skip if not our project
                if not function_name.startswith(self.settings.app_env):
                    continue

                # List event source mappings for this function
                mappings_response = self.lambda_client.list_event_source_mappings(
                    FunctionName=function_name
                )

                for mapping in mappings_response.get("EventSourceMappings", []):
                    if mapping["State"] == "Disabled":
                        uuid = mapping["UUID"]
                        if not self.dry_run:
                            self.lambda_client.update_event_source_mapping(
                                UUID=uuid,
                                Enabled=True
                            )
                        self.log_action(f"Enabled Lambda event source", f"{function_name}:{uuid}")
                        enabled_count += 1

            return enabled_count

        except ClientError as e:
            logger.error(f"Error enabling Lambda event sources: {e}")
            return 0

    def start_rds_instance(self, db_instance_id: str) -> bool:
        """Start RDS database instance"""
        try:
            if not self.dry_run:
                self.rds_client.start_db_instance(
                    DBInstanceIdentifier=db_instance_id
                )

            self.log_action(f"Started RDS instance", db_instance_id)
            return True

        except ClientError as e:
            logger.error(f"Error starting RDS instance: {e}")
            return False

    def restart_all(self):
        """Perform complete system restart"""
        logger.info("=" * 60)
        logger.info("SYSTEM RESTART INITIATED")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("Running in DRY-RUN mode - no actual changes will be made")

        # Step 1: Start RDS instance
        logger.info("\n[1/3] Starting RDS instance...")
        db_instance_id = f"cti-scraper-{self.settings.app_env}"
        if self.start_rds_instance(db_instance_id):
            logger.info(f"✓ Started RDS instance: {db_instance_id}")
            logger.info("⏳ Waiting for RDS to be available (this may take 5-10 minutes)...")
        else:
            logger.warning("⚠ Failed to start RDS instance")

        # Step 2: Enable EventBridge rules
        logger.info("\n[2/3] Enabling EventBridge rules...")
        enabled_rules = self.enable_eventbridge_rules()
        logger.info(f"✓ Enabled {enabled_rules} EventBridge rule(s)")

        # Step 3: Enable Lambda event sources
        logger.info("\n[3/3] Enabling Lambda event sources...")
        enabled_lambdas = self.enable_lambda_event_sources()
        logger.info(f"✓ Enabled {enabled_lambdas} Lambda event source(s)")

        logger.info("\n" + "=" * 60)
        logger.info("SYSTEM RESTART COMPLETE")
        logger.info("=" * 60)
        logger.info("\nNote: ECS tasks will be restarted automatically by the ECS service.")
        logger.info("Web UI should be accessible in a few minutes.")


def main():
    parser = argparse.ArgumentParser(
        description="Restart CTI Scraper after emergency shutdown"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )

    args = parser.parse_args()

    # Confirm if not dry-run
    if not args.dry_run:
        logger.info("\n📢 This will restart all CTI Scraper resources.")
        logger.info("Please ensure that cost issues have been resolved before proceeding.\n")

        response = input("Are you sure you want to proceed? (type 'yes' to confirm): ")
        if response.lower() != "yes":
            logger.info("Restart cancelled.")
            return

    restart = SystemRestart(dry_run=args.dry_run)
    restart.restart_all()


if __name__ == "__main__":
    main()
