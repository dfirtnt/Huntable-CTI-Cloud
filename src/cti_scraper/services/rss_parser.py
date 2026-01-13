"""RSS Feed Parser Service"""
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import feedparser
from feedparser import FeedParserDict

logger = logging.getLogger(__name__)


class RSSParserService:
    """Service for parsing RSS/Atom feeds"""

    def __init__(self):
        self.user_agent = "CTI-Scraper/1.0 (Threat Intelligence Aggregator)"

    def parse_feed(self, feed_url: str) -> Dict[str, any]:
        """Parse an RSS/Atom feed and return articles

        Args:
            feed_url: URL of the RSS/Atom feed

        Returns:
            Dictionary with feed metadata and list of parsed articles
        """
        try:
            logger.info(f"Parsing RSS feed: {feed_url}")

            # Parse the feed with custom user agent
            feed = feedparser.parse(feed_url, agent=self.user_agent)

            # Check for feed parsing errors
            if feed.bozo:
                logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")

            # Extract feed metadata
            feed_info = self._extract_feed_metadata(feed)

            # Extract articles from feed entries
            articles = []
            for entry in feed.entries:
                try:
                    article = self._parse_entry(entry, feed_url)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing entry from {feed_url}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(articles)} articles from {feed_url}")

            return {
                "feed_info": feed_info,
                "articles": articles,
                "success": True,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error parsing RSS feed {feed_url}: {e}")
            return {
                "feed_info": {},
                "articles": [],
                "success": False,
                "error": str(e),
            }

    def _extract_feed_metadata(self, feed: FeedParserDict) -> Dict[str, any]:
        """Extract metadata from feed"""
        feed_data = feed.get("feed", {})

        return {
            "title": feed_data.get("title", ""),
            "link": feed_data.get("link", ""),
            "description": feed_data.get("description", ""),
            "language": feed_data.get("language", "en"),
            "updated": self._parse_date(feed_data.get("updated")),
        }

    def _parse_entry(self, entry: Dict, feed_url: str) -> Optional[Dict[str, any]]:
        """Parse a single feed entry into article format

        Args:
            entry: Feed entry dictionary from feedparser
            feed_url: Source feed URL for reference

        Returns:
            Dictionary with article data or None if parsing fails
        """
        # Extract article URL (required)
        article_url = entry.get("link") or entry.get("id")
        if not article_url:
            logger.warning(f"Entry missing URL in feed {feed_url}")
            return None

        # Extract title (required)
        title = entry.get("title", "").strip()
        if not title:
            logger.warning(f"Entry missing title: {article_url}")
            return None

        # Extract content (try multiple fields)
        content = self._extract_content(entry)
        summary = entry.get("summary", "").strip()

        # Extract published date
        published_date = self._parse_date(
            entry.get("published") or entry.get("updated")
        )

        # Extract authors
        authors = self._extract_authors(entry)

        # Generate content hash for deduplication
        content_hash = self._generate_content_hash(title, article_url, content)

        return {
            "url": article_url,
            "title": title,
            "summary": summary,
            "content": content,
            "published_date": published_date,
            "authors": authors,
            "content_hash": content_hash,
            "source_feed_url": feed_url,
        }

    def _extract_content(self, entry: Dict) -> str:
        """Extract full content from entry, trying multiple fields"""
        # Try content field (most detailed)
        if "content" in entry and entry.content:
            # content is usually a list of dicts with 'value' key
            if isinstance(entry.content, list) and len(entry.content) > 0:
                return entry.content[0].get("value", "").strip()

        # Try summary_detail
        if "summary_detail" in entry:
            summary_detail = entry.summary_detail
            if isinstance(summary_detail, dict):
                return summary_detail.get("value", "").strip()

        # Fall back to summary
        return entry.get("summary", "").strip()

    def _extract_authors(self, entry: Dict) -> List[str]:
        """Extract author names from entry"""
        authors = []

        # Try author field
        if "author" in entry and entry.author:
            authors.append(entry.author.strip())

        # Try authors list
        if "authors" in entry and entry.authors:
            for author in entry.authors:
                if isinstance(author, dict):
                    name = author.get("name", "").strip()
                    if name:
                        authors.append(name)
                elif isinstance(author, str):
                    authors.append(author.strip())

        return authors

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None

        try:
            # feedparser provides parsed time tuples
            if isinstance(date_str, str):
                # Try common date formats
                from dateutil import parser
                return parser.parse(date_str)
            return None
        except Exception as e:
            logger.warning(f"Could not parse date: {date_str} - {e}")
            return None

    def _generate_content_hash(self, title: str, url: str, content: str) -> str:
        """Generate SHA-256 hash for deduplication

        Uses combination of title, URL, and first 500 chars of content
        """
        # Normalize inputs
        title_norm = title.lower().strip()
        url_norm = url.lower().strip()
        content_norm = content[:500].lower().strip() if content else ""

        # Combine and hash
        combined = f"{title_norm}|{url_norm}|{content_norm}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def validate_feed_url(self, feed_url: str) -> bool:
        """Validate that a URL is properly formatted"""
        try:
            result = urlparse(feed_url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    async def parse_feed_async(self, feed_url: str) -> Dict[str, any]:
        """Async wrapper for parse_feed (runs in executor)"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.parse_feed, feed_url)
