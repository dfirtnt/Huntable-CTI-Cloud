"""Scraper Orchestrator - Coordinates RSS and web scraping"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti_scraper.config.sources import get_active_sources, get_sources_with_rss, get_sources_without_rss
from cti_scraper.db.models import Source, Article, SourceCheck
from cti_scraper.services.rss_parser import RSSParserService
from cti_scraper.services.web_scraper import WebScraperService
from cti_scraper.services.hunt_scorer import HuntScorer

logger = logging.getLogger(__name__)


class ScraperOrchestrator:
    """Orchestrates scraping from all configured sources"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.rss_parser = RSSParserService()
        self.web_scraper = WebScraperService()

    async def scrape_all_sources(self) -> Dict[str, any]:
        """Scrape all active sources (RSS and web)

        Returns:
            Summary of scraping results
        """
        logger.info("Starting scrape of all active sources")
        start_time = datetime.utcnow()

        # Get active sources
        rss_sources = get_sources_with_rss()
        web_sources = get_sources_without_rss()

        results = {
            "start_time": start_time.isoformat(),
            "rss_sources": len(rss_sources),
            "web_sources": len(web_sources),
            "total_articles_found": 0,
            "new_articles_saved": 0,
            "duplicate_articles_skipped": 0,
            "errors": [],
        }

        # Scrape RSS sources
        logger.info(f"Scraping {len(rss_sources)} RSS sources")
        for source_config in rss_sources:
            try:
                await self._scrape_rss_source(source_config, results)
            except Exception as e:
                logger.error(f"Error scraping RSS source {source_config['identifier']}: {e}")
                results["errors"].append({
                    "source": source_config["identifier"],
                    "error": str(e),
                })

        # Scrape web sources
        logger.info(f"Scraping {len(web_sources)} web sources")
        for source_config in web_sources:
            try:
                await self._scrape_web_source(source_config, results)
            except Exception as e:
                logger.error(f"Error scraping web source {source_config['identifier']}: {e}")
                results["errors"].append({
                    "source": source_config["identifier"],
                    "error": str(e),
                })

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = duration

        logger.info(
            f"Scraping complete: {results['new_articles_saved']} new articles, "
            f"{results['duplicate_articles_skipped']} duplicates skipped, "
            f"{len(results['errors'])} errors in {duration:.2f}s"
        )

        return results

    async def _scrape_rss_source(self, source_config: Dict, results: Dict):
        """Scrape a single RSS source"""
        identifier = source_config["identifier"]
        rss_url = source_config["rss_url"]

        logger.debug(f"Scraping RSS source: {identifier}")

        # Get or create source record
        source = await self._get_or_create_source(source_config)

        # Check if we should scrape based on frequency
        if not self._should_scrape(source, source_config["check_frequency"]):
            logger.debug(f"Skipping {identifier} - checked recently")
            return

        start_time = datetime.utcnow()

        # Parse RSS feed
        feed_result = await self.rss_parser.parse_feed_async(rss_url)

        if not feed_result["success"]:
            results["errors"].append({
                "source": identifier,
                "error": feed_result["error"],
            })
            # Record failed check
            await self._record_source_check(source.id, False, "rss", 0, feed_result["error"], start_time)
            source.last_check = datetime.utcnow()
            source.consecutive_failures += 1
            await self.db.commit()
            return

        # Process articles
        articles = feed_result["articles"]
        results["total_articles_found"] += len(articles)
        new_count = 0

        for article_data in articles:
            try:
                is_new = await self._save_article(article_data, source.id)
                if is_new:
                    results["new_articles_saved"] += 1
                    new_count += 1
                else:
                    results["duplicate_articles_skipped"] += 1
            except Exception as e:
                logger.error(f"Error saving article from {identifier}: {e}")

        # Update source stats
        source.last_check = datetime.utcnow()
        source.last_success = datetime.utcnow()
        source.consecutive_failures = 0
        source.total_articles += new_count

        # Record successful check
        await self._record_source_check(source.id, True, "rss", len(articles), None, start_time)
        await self.db.commit()

    async def _scrape_web_source(self, source_config: Dict, results: Dict):
        """Scrape a single web source without RSS"""
        identifier = source_config["identifier"]
        url = source_config["url"]

        logger.debug(f"Scraping web source: {identifier}")

        # Get or create source record
        source = await self._get_or_create_source(source_config)

        # Check if we should scrape based on frequency
        if not self._should_scrape(source, source_config["check_frequency"]):
            logger.debug(f"Skipping {identifier} - checked recently")
            return

        start_time = datetime.utcnow()

        # Scrape webpage
        scrape_result = await self.web_scraper.scrape_page(url)

        if not scrape_result["success"]:
            results["errors"].append({
                "source": identifier,
                "error": scrape_result["error"],
            })
            # Record failed check
            await self._record_source_check(source.id, False, "scrape", 0, scrape_result["error"], start_time)
            source.last_check = datetime.utcnow()
            source.consecutive_failures += 1
            await self.db.commit()
            return

        # Process articles
        articles = scrape_result["articles"]
        results["total_articles_found"] += len(articles)
        new_count = 0

        for article_data in articles:
            try:
                is_new = await self._save_article(article_data, source.id)
                if is_new:
                    results["new_articles_saved"] += 1
                    new_count += 1
                else:
                    results["duplicate_articles_skipped"] += 1
            except Exception as e:
                logger.error(f"Error saving article from {identifier}: {e}")

        # Update source stats
        source.last_check = datetime.utcnow()
        source.last_success = datetime.utcnow()
        source.consecutive_failures = 0
        source.total_articles += new_count

        # Record successful check
        await self._record_source_check(source.id, True, "scrape", len(articles), None, start_time)
        await self.db.commit()

    async def _get_or_create_source(self, source_config: Dict) -> Source:
        """Get existing source or create new one"""
        identifier = source_config["identifier"]

        # Try to find existing source
        result = await self.db.execute(
            select(Source).where(Source.identifier == identifier)
        )
        source = result.scalar_one_or_none()

        if source:
            # Update existing source if config changed
            source.name = source_config["name"]
            source.url = source_config["url"]
            source.rss_url = source_config.get("rss_url")
            source.check_frequency = source_config["check_frequency"]
            source.active = source_config["active"]
        else:
            # Create new source
            source = Source(
                identifier=identifier,
                name=source_config["name"],
                url=source_config["url"],
                rss_url=source_config.get("rss_url"),
                check_frequency=source_config["check_frequency"],
                active=source_config["active"],
            )
            self.db.add(source)

        await self.db.commit()
        await self.db.refresh(source)
        return source

    def _should_scrape(self, source: Source, check_frequency: int) -> bool:
        """Determine if source should be scraped based on last check time"""
        if not source.last_check:
            return True

        time_since_check = datetime.utcnow() - source.last_check.replace(tzinfo=None)
        return time_since_check.total_seconds() >= check_frequency

    async def _record_source_check(
        self,
        source_id: int,
        success: bool,
        method: str,
        articles_found: int,
        error_message: Optional[str],
        start_time: datetime
    ):
        """Record a source check in the history"""
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000  # ms
        check = SourceCheck(
            source_id=source_id,
            success=success,
            method=method,
            articles_found=articles_found,
            response_time=response_time,
            error_message=error_message,
        )
        self.db.add(check)

    async def _save_article(self, article_data: Dict, source_id: int) -> bool:
        """Save article to database if not duplicate

        Returns:
            True if new article was saved, False if duplicate
        """
        content_hash = article_data["content_hash"]

        # Check for existing article by hash
        result = await self.db.execute(
            select(Article).where(Article.content_hash == content_hash)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.debug(f"Duplicate article found: {article_data['title'][:50]}")
            return False

        # Calculate hunt score
        content = article_data.get("content", "")
        summary = article_data.get("summary", "")
        title = article_data["title"]
        hunt_result = HuntScorer.score_article(title, summary, content)

        # Calculate word count
        word_count = len(content.split()) if content else 0

        # Create new article
        article = Article(
            source_id=source_id,
            canonical_url=article_data["url"],
            title=title,
            summary=summary,
            content=content,
            published_at=article_data.get("published_date"),
            authors=article_data.get("authors", []),
            content_hash=content_hash,
            word_count=word_count,
            article_metadata={
                "source_feed_url": article_data.get("source_feed_url"),
                "source_url": article_data.get("source_url"),
                "hunt_score": hunt_result["threat_hunting_score"],
                "perfect_keywords": hunt_result["perfect_keyword_matches"][:10],
                "good_keywords": hunt_result["good_keyword_matches"][:10],
                "lolbas_matches": hunt_result["lolbas_matches"][:10],
                "intelligence_matches": hunt_result["intelligence_matches"][:10],
            },
            processing_status="scraped",
        )

        self.db.add(article)
        await self.db.commit()

        logger.info(f"Saved new article: {article.title[:50]}... (hunt_score: {hunt_result['threat_hunting_score']})")
        return True

    async def scrape_source_by_identifier(self, identifier: str) -> Dict[str, any]:
        """Scrape a single source by identifier

        Args:
            identifier: Source identifier (e.g., 'microsoft-security-blog')

        Returns:
            Scraping results for that source
        """
        from cti_scraper.config.sources import get_source_by_identifier

        source_config = get_source_by_identifier(identifier)
        if not source_config:
            return {
                "success": False,
                "error": f"Source not found: {identifier}",
            }

        if not source_config["active"]:
            return {
                "success": False,
                "error": f"Source is not active: {identifier}",
            }

        results = {
            "source": identifier,
            "total_articles_found": 0,
            "new_articles_saved": 0,
            "duplicate_articles_skipped": 0,
            "errors": [],
        }

        try:
            if source_config.get("rss_url"):
                await self._scrape_rss_source(source_config, results)
            else:
                await self._scrape_web_source(source_config, results)

            results["success"] = True
        except Exception as e:
            logger.error(f"Error scraping {identifier}: {e}")
            results["success"] = False
            results["error"] = str(e)

        return results
