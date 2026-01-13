#!/usr/bin/env python3
"""
Emergency Shutdown Script

This script performs an emergency shutdown of all CTI Scraper resources
to prevent further AWS costs. Use this if costs are approaching the $100/month limit.

Usage:
    python scripts/emergency_shutdown.py [--dry-run] [--skip-backup]

Options:
    --dry-run: Show what would be done without actually doing it
    --skip-backup: Skip database backup before shutdown
"""
import argparse
import logging
import sys
from datetime import datetime
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


class EmergencyShutdown:
    """Handle emergency shutdown of all resources"""

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

    def disable_eventbridge_rules(self) -> int:
        """Disable all EventBridge rules for the project"""
        try:
            self.log_action("Checking EventBridge rules")
            response = self.events_client.list_rules(NamePrefix=f"{self.settings.app_env}-")

            disabled_count = 0
            for rule in response.get("Rules", []):
                rule_name = rule["Name"]
                if rule["State"] == "ENABLED":
                    if not self.dry_run:
                        self.events_client.disable_rule(Name=rule_name)
                    self.log_action(f"Disabled EventBridge rule", rule_name)
                    disabled_count += 1

            return disabled_count

        except ClientError as e:
            logger.error(f"Error disabling EventBridge rules: {e}")
            return 0

    def stop_ecs_tasks(self) -> int:
        """Stop all ECS tasks for the project"""
        try:
            self.log_action("Checking ECS tasks")

            # List clusters
            clusters_response = self.ecs_client.list_clusters()
            stopped_count = 0

            for cluster_arn in clusters_response.get("clusterArns", []):
                # List tasks in cluster
                tasks_response = self.ecs_client.list_tasks(
                    cluster=cluster_arn,
                    desiredStatus="RUNNING"
                )

                for task_arn in tasks_response.get("taskArns", []):
                    if not self.dry_run:
                        self.ecs_client.stop_task(
                            cluster=cluster_arn,
                            task=task_arn,
                            reason="Emergency shutdown - cost limit approaching"
                        )
                    self.log_action(f"Stopped ECS task", task_arn)
                    stopped_count += 1

            return stopped_count

        except ClientError as e:
            logger.error(f"Error stopping ECS tasks: {e}")
            return 0

    def disable_lambda_event_sources(self) -> int:
        """Disable Lambda event source mappings"""
        try:
            self.log_action("Checking Lambda event sources")

            # List all Lambda functions
            functions_response = self.lambda_client.list_functions()
            disabled_count = 0

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
                    if mapping["State"] == "Enabled":
                        uuid = mapping["UUID"]
                        if not self.dry_run:
                            self.lambda_client.update_event_source_mapping(
                                UUID=uuid,
                                Enabled=False
                            )
                        self.log_action(f"Disabled Lambda event source", f"{function_name}:{uuid}")
                        disabled_count += 1

            return disabled_count

        except ClientError as e:
            logger.error(f"Error disabling Lambda event sources: {e}")
            return 0

    def create_rds_snapshot(self, db_instance_id: str) -> str:
        """Create RDS snapshot before shutdown"""
        try:
            snapshot_id = f"{db_instance_id}-emergency-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

            if not self.dry_run:
                self.rds_client.create_db_snapshot(
                    DBSnapshotIdentifier=snapshot_id,
                    DBInstanceIdentifier=db_instance_id,
                    Tags=[
                        {"Key": "Type", "Value": "EmergencyBackup"},
                        {"Key": "Timestamp", "Value": datetime.utcnow().isoformat()},
                    ]
                )

            self.log_action(f"Created RDS snapshot", snapshot_id)
            return snapshot_id

        except ClientError as e:
            logger.error(f"Error creating RDS snapshot: {e}")
            return ""

    def stop_rds_instance(self, db_instance_id: str) -> bool:
        """Stop RDS database instance"""
        try:
            if not self.dry_run:
                self.rds_client.stop_db_instance(
                    DBInstanceIdentifier=db_instance_id
                )

            self.log_action(f"Stopped RDS instance", db_instance_id)
            return True

        except ClientError as e:
            logger.error(f"Error stopping RDS instance: {e}")
            return False

    def shutdown_all(self, skip_backup: bool = False):
        """Perform complete emergency shutdown"""
        logger.info("=" * 60)
        logger.info("EMERGENCY SHUTDOWN INITIATED")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("Running in DRY-RUN mode - no actual changes will be made")

        # Step 1: Disable EventBridge rules (stop scheduled tasks)
        logger.info("\n[1/5] Disabling EventBridge rules...")
        disabled_rules = self.disable_eventbridge_rules()
        logger.info(f"✓ Disabled {disabled_rules} EventBridge rule(s)")

        # Step 2: Disable Lambda event sources
        logger.info("\n[2/5] Disabling Lambda event sources...")
        disabled_lambdas = self.disable_lambda_event_sources()
        logger.info(f"✓ Disabled {disabled_lambdas} Lambda event source(s)")

        # Step 3: Stop ECS tasks
        logger.info("\n[3/5] Stopping ECS tasks...")
        stopped_tasks = self.stop_ecs_tasks()
        logger.info(f"✓ Stopped {stopped_tasks} ECS task(s)")

        # Step 4: Backup RDS (if not skipped)
        if not skip_backup:
            logger.info("\n[4/5] Creating RDS backup...")
            # You'll need to specify your actual DB instance ID
            db_instance_id = f"cti-scraper-{self.settings.app_env}"
            snapshot_id = self.create_rds_snapshot(db_instance_id)
            if snapshot_id:
                logger.info(f"✓ Created snapshot: {snapshot_id}")
            else:
                logger.warning("⚠ Failed to create RDS snapshot")
        else:
            logger.info("\n[4/5] Skipping RDS backup (--skip-backup flag)")

        # Step 5: Stop RDS instance
        logger.info("\n[5/5] Stopping RDS instance...")
        db_instance_id = f"cti-scraper-{self.settings.app_env}"
        if self.stop_rds_instance(db_instance_id):
            logger.info(f"✓ Stopped RDS instance: {db_instance_id}")
        else:
            logger.warning("⚠ Failed to stop RDS instance")

        logger.info("\n" + "=" * 60)
        logger.info("EMERGENCY SHUTDOWN COMPLETE")
        logger.info("=" * 60)
        logger.info("\nAll resources have been shut down to prevent further costs.")
        logger.info("To restart the system, run: python scripts/restart_system.py")


def main():
    parser = argparse.ArgumentParser(
        description="Emergency shutdown of CTI Scraper to prevent cost overruns"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip database backup before shutdown (not recommended)"
    )

    args = parser.parse_args()

    # Confirm if not dry-run
    if not args.dry_run:
        logger.warning("\n⚠️  WARNING: This will shut down all CTI Scraper resources!")
        logger.warning("This action should only be taken if costs are approaching the budget limit.\n")

        response = input("Are you sure you want to proceed? (type 'yes' to confirm): ")
        if response.lower() != "yes":
            logger.info("Shutdown cancelled.")
            return

    shutdown = EmergencyShutdown(dry_run=args.dry_run)
    shutdown.shutdown_all(skip_backup=args.skip_backup)


if __name__ == "__main__":
    main()
