"""Web Scraper Service for sites without RSS feeds"""
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class WebScraperService:
    """Service for scraping threat intelligence websites"""

    def __init__(self):
        self.user_agent = "CTI-Scraper/1.0 (Threat Intelligence Aggregator)"
        self.timeout = aiohttp.ClientTimeout(total=30)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def scrape_page(
        self, url: str, selector_config: Optional[Dict] = None
    ) -> Dict[str, any]:
        """Scrape a webpage and extract articles

        Args:
            url: URL to scrape
            selector_config: Optional dict with CSS selectors for targeted extraction

        Returns:
            Dictionary with extracted articles and metadata
        """
        try:
            logger.info(f"Scraping webpage: {url}")

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    ssl=True,
                ) as response:
                    response.raise_for_status()
                    html = await response.text()

            # Parse HTML
            soup = BeautifulSoup(html, "lxml")

            # Extract articles based on configuration or use generic extraction
            if selector_config:
                articles = self._extract_with_selectors(soup, url, selector_config)
            else:
                articles = self._extract_generic(soup, url)

            logger.info(f"Successfully scraped {len(articles)} articles from {url}")

            return {
                "articles": articles,
                "success": True,
                "error": None,
            }

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error scraping {url}: {e}")
            return {
                "articles": [],
                "success": False,
                "error": f"HTTP error: {str(e)}",
            }
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "articles": [],
                "success": False,
                "error": str(e),
            }

    def _extract_with_selectors(
        self, soup: BeautifulSoup, base_url: str, config: Dict
    ) -> List[Dict[str, any]]:
        """Extract articles using configured CSS selectors

        Config format:
        {
            "article_selector": ".article",
            "title_selector": "h2.title",
            "link_selector": "a.permalink",
            "date_selector": "time.published",
            "summary_selector": "p.excerpt"
        }
        """
        articles = []

        # Find all article containers
        article_containers = soup.select(config.get("article_selector", "article"))

        for container in article_containers:
            try:
                # Extract title
                title_elem = container.select_one(config.get("title_selector", "h2"))
                title = title_elem.get_text(strip=True) if title_elem else None

                # Extract link
                link_elem = container.select_one(config.get("link_selector", "a"))
                if link_elem and link_elem.get("href"):
                    article_url = urljoin(base_url, link_elem["href"])
                else:
                    continue  # Skip if no link

                # Extract date
                date_elem = container.select_one(config.get("date_selector", "time"))
                published_date = None
                if date_elem:
                    # Try datetime attribute first
                    date_str = date_elem.get("datetime") or date_elem.get_text(strip=True)
                    published_date = self._parse_date(date_str)

                # Extract summary
                summary_elem = container.select_one(config.get("summary_selector", "p"))
                summary = summary_elem.get_text(strip=True) if summary_elem else ""

                if title and article_url:
                    articles.append({
                        "url": article_url,
                        "title": title,
                        "summary": summary,
                        "content": summary,  # Full content requires separate fetch
                        "published_date": published_date,
                        "authors": [],
                        "content_hash": self._generate_content_hash(title, article_url, summary),
                        "source_url": base_url,
                    })

            except Exception as e:
                logger.warning(f"Error extracting article from container: {e}")
                continue

        return articles

    def _extract_generic(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, any]]:
        """Generic article extraction without specific selectors

        Looks for common HTML patterns:
        - <article> tags
        - Headings with links
        - Blog post structures
        """
        articles = []

        # Strategy 1: Look for <article> tags
        article_tags = soup.find_all("article")
        for article_tag in article_tags[:20]:  # Limit to 20 per page
            try:
                article = self._extract_from_article_tag(article_tag, base_url)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"Error extracting from article tag: {e}")
                continue

        # Strategy 2: Look for blog post patterns (if no articles found)
        if len(articles) == 0:
            articles = self._extract_blog_posts(soup, base_url)

        return articles

    def _extract_from_article_tag(
        self, article_tag, base_url: str
    ) -> Optional[Dict[str, any]]:
        """Extract article data from an <article> tag"""
        # Find title (usually h1, h2, or h3)
        title_elem = article_tag.find(["h1", "h2", "h3"])
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        # Find link (in title or nearby)
        link_elem = title_elem.find("a") or article_tag.find("a")
        if not link_elem or not link_elem.get("href"):
            return None

        article_url = urljoin(base_url, link_elem["href"])

        # Find date
        date_elem = article_tag.find("time") or article_tag.find(
            class_=lambda x: x and any(d in str(x).lower() for d in ["date", "time", "published"])
        )
        published_date = None
        if date_elem:
            date_str = date_elem.get("datetime") or date_elem.get_text(strip=True)
            published_date = self._parse_date(date_str)

        # Find summary/excerpt
        summary = ""
        summary_elem = article_tag.find(
            class_=lambda x: x and any(s in str(x).lower() for s in ["summary", "excerpt", "description"])
        )
        if summary_elem:
            summary = summary_elem.get_text(strip=True)
        else:
            # Fall back to first paragraph
            p_elem = article_tag.find("p")
            if p_elem:
                summary = p_elem.get_text(strip=True)

        return {
            "url": article_url,
            "title": title,
            "summary": summary,
            "content": summary,
            "published_date": published_date,
            "authors": [],
            "content_hash": self._generate_content_hash(title, article_url, summary),
            "source_url": base_url,
        }

    def _extract_blog_posts(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, any]]:
        """Extract blog posts using common patterns"""
        articles = []

        # Find all headings with links (common blog pattern)
        headings = soup.find_all(["h2", "h3"], class_=lambda x: x and "post" in str(x).lower())
        if not headings:
            # Broader search
            headings = soup.find_all(["h2", "h3"])[:20]

        for heading in headings:
            try:
                link = heading.find("a")
                if not link or not link.get("href"):
                    continue

                title = heading.get_text(strip=True)
                article_url = urljoin(base_url, link["href"])

                # Look for nearby date and summary
                parent = heading.parent
                date_elem = parent.find("time") if parent else None
                published_date = None
                if date_elem:
                    date_str = date_elem.get("datetime") or date_elem.get_text(strip=True)
                    published_date = self._parse_date(date_str)

                summary = ""
                if parent:
                    p_elem = parent.find("p")
                    if p_elem:
                        summary = p_elem.get_text(strip=True)

                articles.append({
                    "url": article_url,
                    "title": title,
                    "summary": summary,
                    "content": summary,
                    "published_date": published_date,
                    "authors": [],
                    "content_hash": self._generate_content_hash(title, article_url, summary),
                    "source_url": base_url,
                })

            except Exception as e:
                logger.debug(f"Error extracting blog post: {e}")
                continue

        return articles

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None

        try:
            from dateutil import parser
            return parser.parse(date_str)
        except Exception as e:
            logger.debug(f"Could not parse date: {date_str} - {e}")
            return None

    def _generate_content_hash(self, title: str, url: str, content: str) -> str:
        """Generate SHA-256 hash for deduplication"""
        title_norm = title.lower().strip()
        url_norm = url.lower().strip()
        content_norm = content[:500].lower().strip() if content else ""

        combined = f"{title_norm}|{url_norm}|{content_norm}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    async def fetch_full_article(self, url: str) -> Optional[str]:
        """Fetch full article content from a specific article URL

        This is used after discovering an article to get its full content
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    ssl=True,
                ) as response:
                    response.raise_for_status()
                    html = await response.text()

            soup = BeautifulSoup(html, "lxml")

            # Try to find main content area
            content_area = (
                soup.find("article")
                or soup.find(class_=lambda x: x and "content" in str(x).lower())
                or soup.find("main")
                or soup.find("body")
            )

            if content_area:
                # Extract text from paragraphs
                paragraphs = content_area.find_all("p")
                content = "\n\n".join(p.get_text(strip=True) for p in paragraphs)
                return content

            return None

        except Exception as e:
            logger.error(f"Error fetching full article {url}: {e}")
            return None
