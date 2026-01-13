"""Lambda handler for CTI Scraper

This handler is invoked by EventBridge on a schedule to scrape
threat intelligence sources.

Event types:
- Scheduled: Scrape all sources due for checking
- Manual: Scrape specific source(s) by identifier
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def get_database_url_from_secret() -> str:
    """Fetch database credentials from Secrets Manager and build connection URL"""
    secret_id = os.environ.get("DATABASE_SECRET_ID")
    if not secret_id:
        raise ValueError("DATABASE_SECRET_ID environment variable not set")

    region = os.environ.get("AWS_REGION_NAME", "us-east-1")
    client = boto3.client("secretsmanager", region_name=region)

    response = client.get_secret_value(SecretId=secret_id)
    secret = json.loads(response["SecretString"])

    # Build async database URL
    return (
        f"postgresql+asyncpg://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}"
    )


def setup_database_url():
    """Set DATABASE_URL environment variable from Secrets Manager"""
    if os.environ.get("DATABASE_URL"):
        # Already set (local development)
        return

    try:
        url = get_database_url_from_secret()
        os.environ["DATABASE_URL"] = url
        # Also set sync URL for any sync operations
        os.environ["DATABASE_URL_SYNC"] = url.replace("+asyncpg", "")
        logger.info("Database URL configured from Secrets Manager")
    except Exception as e:
        logger.error(f"Failed to get database URL from Secrets Manager: {e}")
        raise


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda entry point

    Args:
        event: EventBridge or manual invocation event
            Scheduled: {"source": "aws.events", "detail-type": "Scheduled Event"}
            Manual: {"action": "scrape", "sources": ["microsoft-security-blog"]}
            Manual all: {"action": "scrape_all"}
        context: Lambda context

    Returns:
        Scraping results summary
    """
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")

    # Setup database URL from Secrets Manager
    setup_database_url()

    # Run async handler
    result = asyncio.get_event_loop().run_until_complete(
        async_handler(event, context)
    )

    return result


async def async_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Async handler for scraping operations"""
    from cti_scraper.db.base import get_async_session, async_engine
    from cti_scraper.services.scraper_orchestrator import ScraperOrchestrator
    from cti_scraper.config.sources import get_source_by_identifier

    start_time = datetime.utcnow()

    try:
        # Handle migration action
        if event.get("action") == "migrate":
            return await run_migrations(event)

        # Determine action type
        if event.get("source") == "aws.events":
            # Scheduled EventBridge invocation - scrape all due sources
            action = "scrape_all"
            sources = None
        elif event.get("action") == "scrape":
            # Manual invocation with specific sources
            action = "scrape"
            sources = event.get("sources", [])
        elif event.get("action") == "scrape_all":
            # Manual invocation to scrape all
            action = "scrape_all"
            sources = None
        else:
            # Default: scrape all
            action = "scrape_all"
            sources = None

        logger.info(f"Action: {action}, Sources: {sources}")

        async with get_async_session() as session:
            orchestrator = ScraperOrchestrator(session)

            if action == "scrape_all":
                result = await orchestrator.scrape_all_sources()
            else:
                # Scrape specific sources
                result = {
                    "sources_requested": len(sources),
                    "results": [],
                    "errors": [],
                }
                for source_id in sources:
                    try:
                        source_result = await orchestrator.scrape_source_by_identifier(source_id)
                        result["results"].append({
                            "source": source_id,
                            "success": source_result.get("success", False),
                            "new_articles": source_result.get("new_articles_saved", 0),
                        })
                    except Exception as e:
                        logger.error(f"Error scraping {source_id}: {e}")
                        result["errors"].append({
                            "source": source_id,
                            "error": str(e),
                        })

        # Close database connections
        await async_engine.dispose()

        duration = (datetime.utcnow() - start_time).total_seconds()

        response = {
            "statusCode": 200,
            "body": {
                "success": True,
                "action": action,
                "duration_seconds": round(duration, 2),
                "result": result,
            }
        }

        logger.info(f"Scraping completed in {duration:.2f}s: {result.get('new_articles_saved', 0)} new articles")
        return response

    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)

        return {
            "statusCode": 500,
            "body": {
                "success": False,
                "error": str(e),
            }
        }


async def run_migrations(event: Dict[str, Any]) -> Dict[str, Any]:
    """Run Alembic migrations from Lambda

    Args:
        event: {"action": "migrate", "revision": "head"} or {"action": "migrate", "revision": "0002"}

    Returns:
        Migration result
    """
    import subprocess
    import sys

    revision = event.get("revision", "head")
    logger.info(f"Running migrations to revision: {revision}")

    try:
        # Get the sync database URL
        db_url = os.environ.get("DATABASE_URL_SYNC")
        if not db_url:
            raise ValueError("DATABASE_URL_SYNC not set")

        # Run alembic upgrade via subprocess
        # This ensures proper isolation and uses the alembic.ini config
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd="/var/task",  # Lambda task root
        )

        if result.returncode == 0:
            logger.info(f"Migration successful: {result.stdout}")
            return {
                "statusCode": 200,
                "body": {
                    "success": True,
                    "action": "migrate",
                    "revision": revision,
                    "output": result.stdout,
                }
            }
        else:
            logger.error(f"Migration failed: {result.stderr}")
            return {
                "statusCode": 500,
                "body": {
                    "success": False,
                    "action": "migrate",
                    "revision": revision,
                    "error": result.stderr,
                    "output": result.stdout,
                }
            }

    except subprocess.TimeoutExpired:
        logger.error("Migration timed out")
        return {
            "statusCode": 500,
            "body": {
                "success": False,
                "action": "migrate",
                "error": "Migration timed out after 5 minutes",
            }
        }
    except Exception as e:
        logger.error(f"Migration error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": {
                "success": False,
                "action": "migrate",
                "error": str(e),
            }
        }


# For local testing
if __name__ == "__main__":
    # Test scheduled event
    test_event = {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
        "detail": {}
    }

    result = handler(test_event, None)
    print(json.dumps(result, indent=2, default=str))
