"""Test scraper locally"""
import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


async def test_scraper():
    """Test the scraper orchestrator locally"""
    from cti_scraper.services.scraper_orchestrator import ScraperOrchestrator
    from cti_scraper.db.base import get_async_session

    logger.info("Starting local scraper test...")

    async with get_async_session() as session:
        orchestrator = ScraperOrchestrator(session)

        # Test with just one source
        logger.info("Testing Microsoft Security Blog...")
        result = await orchestrator.scrape_source_by_identifier("microsoft-security-blog")

        logger.info(f"Scrape result: {result}")

        return result


if __name__ == "__main__":
    result = asyncio.run(test_scraper())
    print(f"\n✓ Scraper test completed!")
    print(f"Result: {result}")
