"""Scraper API routes - Phase 1"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from cti_scraper.config.sources import (
    get_active_sources,
    get_source_by_identifier,
    get_sources_with_rss,
    get_sources_without_rss,
    THREAT_INTEL_SOURCES,
)
from cti_scraper.db import get_async_session
from cti_scraper.db.models import Article, Source, SourceCheck
from cti_scraper.services.scraper_orchestrator import ScraperOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


# Response models
class SourceInfo(BaseModel):
    identifier: str
    name: str
    url: str
    rss_url: Optional[str]
    check_frequency: int
    active: bool
    has_rss: bool


class SourceStats(BaseModel):
    identifier: str
    name: str
    total_articles: int
    last_check: Optional[datetime]
    last_success: Optional[datetime]
    consecutive_failures: int
    active: bool


class ArticleSummary(BaseModel):
    id: int
    title: str
    canonical_url: str
    source_identifier: str
    source_name: str
    published_at: Optional[datetime]
    discovered_at: datetime
    hunt_score: Optional[float]
    word_count: Optional[int]


class ScrapeResult(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None


# Endpoints
@router.get("/sources", response_model=List[SourceInfo])
async def list_sources(active_only: bool = Query(False, description="Only show active sources")):
    """List all configured threat intelligence sources"""
    sources = THREAT_INTEL_SOURCES if not active_only else get_active_sources()

    return [
        SourceInfo(
            identifier=s["identifier"],
            name=s["name"],
            url=s["url"],
            rss_url=s.get("rss_url"),
            check_frequency=s["check_frequency"],
            active=s["active"],
            has_rss=s.get("rss_url") is not None,
        )
        for s in sources
    ]


@router.get("/sources/stats", response_model=List[SourceStats])
async def get_source_stats():
    """Get statistics for all sources from the database"""
    async with get_async_session() as session:
        result = await session.execute(
            select(Source).order_by(Source.name)
        )
        sources = result.scalars().all()

        return [
            SourceStats(
                identifier=s.identifier,
                name=s.name,
                total_articles=s.total_articles,
                last_check=s.last_check,
                last_success=s.last_success,
                consecutive_failures=s.consecutive_failures,
                active=s.active,
            )
            for s in sources
        ]


@router.get("/sources/{identifier}")
async def get_source_detail(identifier: str):
    """Get detailed information about a specific source"""
    # Get config
    config = get_source_by_identifier(identifier)
    if not config:
        raise HTTPException(status_code=404, detail=f"Source not found: {identifier}")

    # Get database stats
    async with get_async_session() as session:
        result = await session.execute(
            select(Source).where(Source.identifier == identifier)
        )
        db_source = result.scalar_one_or_none()

        # Get recent checks
        recent_checks = []
        if db_source:
            checks_result = await session.execute(
                select(SourceCheck)
                .where(SourceCheck.source_id == db_source.id)
                .order_by(desc(SourceCheck.check_time))
                .limit(10)
            )
            recent_checks = [
                {
                    "check_time": c.check_time,
                    "success": c.success,
                    "method": c.method,
                    "articles_found": c.articles_found,
                    "response_time_ms": c.response_time,
                    "error": c.error_message,
                }
                for c in checks_result.scalars().all()
            ]

    return {
        "config": config,
        "database_stats": {
            "total_articles": db_source.total_articles if db_source else 0,
            "last_check": db_source.last_check if db_source else None,
            "last_success": db_source.last_success if db_source else None,
            "consecutive_failures": db_source.consecutive_failures if db_source else 0,
        } if db_source else None,
        "recent_checks": recent_checks,
    }


@router.post("/scrape/all", response_model=ScrapeResult)
async def scrape_all_sources(background_tasks: BackgroundTasks):
    """Trigger scraping of all active sources (runs in background)"""
    async def run_scrape():
        async with get_async_session() as session:
            orchestrator = ScraperOrchestrator(session)
            result = await orchestrator.scrape_all_sources()
            logger.info(f"Scrape completed: {result}")

    background_tasks.add_task(run_scrape)

    return ScrapeResult(
        success=True,
        message="Scraping started in background for all active sources",
        details={
            "rss_sources": len(get_sources_with_rss()),
            "web_sources": len(get_sources_without_rss()),
        }
    )


@router.post("/scrape/{identifier}", response_model=ScrapeResult)
async def scrape_single_source(identifier: str):
    """Scrape a single source by identifier (synchronous)"""
    config = get_source_by_identifier(identifier)
    if not config:
        raise HTTPException(status_code=404, detail=f"Source not found: {identifier}")

    async with get_async_session() as session:
        orchestrator = ScraperOrchestrator(session)
        result = await orchestrator.scrape_source_by_identifier(identifier)

    return ScrapeResult(
        success=result.get("success", False),
        message=f"Scraped {identifier}",
        details=result,
    )


@router.get("/articles", response_model=List[ArticleSummary])
async def list_articles(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None, description="Filter by source identifier"),
    min_hunt_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum hunt score"),
    sort_by: str = Query("discovered_at", description="Sort field: discovered_at, published_at, hunt_score"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
):
    """List scraped articles with filtering and pagination"""
    async with get_async_session() as session:
        # Build query
        query = select(Article, Source).join(Source, Article.source_id == Source.id)

        # Apply filters
        if source:
            query = query.where(Source.identifier == source)

        if min_hunt_score is not None:
            # Filter by hunt_score in article_metadata JSONB
            query = query.where(
                Article.article_metadata["hunt_score"].astext.cast(float) >= min_hunt_score
            )

        # Apply sorting
        sort_column = {
            "discovered_at": Article.discovered_at,
            "published_at": Article.published_at,
            "hunt_score": Article.article_metadata["hunt_score"].astext.cast(float),
        }.get(sort_by, Article.discovered_at)

        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        rows = result.all()

        return [
            ArticleSummary(
                id=article.id,
                title=article.title,
                canonical_url=article.canonical_url,
                source_identifier=source_obj.identifier,
                source_name=source_obj.name,
                published_at=article.published_at,
                discovered_at=article.discovered_at,
                hunt_score=article.article_metadata.get("hunt_score") if article.article_metadata else None,
                word_count=article.word_count,
            )
            for article, source_obj in rows
        ]


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    """Get full article details by ID"""
    async with get_async_session() as session:
        result = await session.execute(
            select(Article, Source)
            .join(Source, Article.source_id == Source.id)
            .where(Article.id == article_id)
        )
        row = result.first()

        if not row:
            raise HTTPException(status_code=404, detail=f"Article not found: {article_id}")

        article, source = row

        return {
            "id": article.id,
            "title": article.title,
            "canonical_url": article.canonical_url,
            "summary": article.summary,
            "content": article.content,
            "published_at": article.published_at,
            "discovered_at": article.discovered_at,
            "authors": article.authors,
            "tags": article.tags,
            "word_count": article.word_count,
            "content_hash": article.content_hash,
            "processing_status": article.processing_status,
            "article_metadata": article.article_metadata,
            "source": {
                "identifier": source.identifier,
                "name": source.name,
                "url": source.url,
            },
        }


@router.get("/stats/summary")
async def get_scraper_stats():
    """Get overall scraper statistics"""
    async with get_async_session() as session:
        # Total articles
        total_articles = await session.execute(
            select(func.count(Article.id))
        )
        total_count = total_articles.scalar()

        # Articles by source
        articles_by_source = await session.execute(
            select(Source.identifier, Source.name, func.count(Article.id))
            .join(Article, Source.id == Article.source_id)
            .group_by(Source.id)
            .order_by(desc(func.count(Article.id)))
        )

        # Articles in last 24 hours
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_articles = await session.execute(
            select(func.count(Article.id))
            .where(Article.discovered_at >= yesterday)
        )
        recent_count = recent_articles.scalar()

        # Source health
        sources = await session.execute(select(Source))
        source_list = sources.scalars().all()
        healthy_sources = sum(1 for s in source_list if s.consecutive_failures == 0)

        # Average hunt score
        avg_score = await session.execute(
            select(func.avg(Article.article_metadata["hunt_score"].astext.cast(float)))
            .where(Article.article_metadata.isnot(None))
        )

        return {
            "total_articles": total_count,
            "articles_last_24h": recent_count,
            "configured_sources": len(THREAT_INTEL_SOURCES),
            "active_sources": len(get_active_sources()),
            "healthy_sources": healthy_sources,
            "sources_with_issues": len(source_list) - healthy_sources if source_list else 0,
            "average_hunt_score": round(avg_score.scalar() or 0, 1),
            "articles_by_source": [
                {"identifier": row[0], "name": row[1], "count": row[2]}
                for row in articles_by_source.all()
            ],
        }
