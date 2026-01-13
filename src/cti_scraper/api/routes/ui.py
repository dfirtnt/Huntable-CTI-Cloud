"""Web UI routes for articles, dashboard, sources"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select

from cti_scraper.config.sources import THREAT_INTEL_SOURCES, get_active_sources
from cti_scraper.db import get_async_session
from cti_scraper.db.models import Article, Source

logger = logging.getLogger(__name__)
router = APIRouter()

# Setup Jinja2 templates
templates = Jinja2Templates(directory="src/cti_scraper/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard homepage with statistics"""
    async with get_async_session() as session:
        # Total articles
        total_articles = await session.execute(select(func.count(Article.id)))
        total_count = total_articles.scalar()

        # Articles by source (top 10)
        articles_by_source = await session.execute(
            select(Source.name, func.count(Article.id).label("count"))
            .join(Article, Source.id == Article.source_id)
            .group_by(Source.id, Source.name)
            .order_by(desc("count"))
            .limit(10)
        )

        # Articles in last 24 hours
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_articles = await session.execute(
            select(func.count(Article.id)).where(Article.discovered_at >= yesterday)
        )
        recent_count = recent_articles.scalar()

        # Source health
        sources = await session.execute(select(Source))
        source_list = sources.scalars().all()
        healthy_sources = sum(1 for s in source_list if s.consecutive_failures == 0)

        # Average hunt score
        avg_score_result = await session.execute(
            select(func.avg(Article.article_metadata["hunt_score"].astext.cast(func.numeric)))
            .where(Article.article_metadata.isnot(None))
        )
        avg_score = avg_score_result.scalar()

        # Recent articles (last 10)
        recent_query = (
            select(Article, Source)
            .join(Source, Article.source_id == Source.id)
            .order_by(desc(Article.discovered_at))
            .limit(10)
        )
        recent_result = await session.execute(recent_query)
        recent_articles_list = [
            {
                "id": article.id,
                "title": article.title,
                "source_name": source.name,
                "published_at": article.published_at,
                "hunt_score": article.article_metadata.get("hunt_score") if article.article_metadata else None,
                "word_count": article.word_count,
            }
            for article, source in recent_result.all()
        ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_articles": total_count,
            "articles_last_24h": recent_count,
            "configured_sources": len(THREAT_INTEL_SOURCES),
            "active_sources": len(get_active_sources()),
            "healthy_sources": healthy_sources,
            "sources_with_issues": len(source_list) - healthy_sources if source_list else 0,
            "average_hunt_score": round(avg_score, 1) if avg_score else 0,
            "articles_by_source": [
                {"name": row[0], "count": row[1]} for row in articles_by_source.all()
            ],
            "recent_articles": recent_articles_list,
        },
    )


@router.get("/articles", response_class=HTMLResponse)
async def articles_list(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    source: Optional[str] = Query(None),
    min_hunt_score: Optional[float] = Query(None, ge=0, le=100),
    search: Optional[str] = Query(None),
    sort_by: str = Query("discovered_at"),
):
    """Articles list page with filters and pagination"""
    async with get_async_session() as session:
        # Build query
        query = select(Article, Source).join(Source, Article.source_id == Source.id)

        # Apply filters
        if source:
            query = query.where(Source.identifier == source)

        if min_hunt_score is not None:
            query = query.where(
                Article.article_metadata["hunt_score"].astext.cast(func.numeric) >= min_hunt_score
            )

        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Article.title.ilike(search_term)) | (Article.summary.ilike(search_term))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total_articles = total_result.scalar()

        # Apply sorting
        sort_column = {
            "discovered_at": Article.discovered_at,
            "published_at": Article.published_at,
            "hunt_score": Article.article_metadata["hunt_score"].astext.cast(func.numeric),
            "word_count": Article.word_count,
        }.get(sort_by, Article.discovered_at)
        query = query.order_by(desc(sort_column))

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        result = await session.execute(query)
        articles = [
            {
                "id": article.id,
                "title": article.title,
                "canonical_url": article.canonical_url,
                "source_name": source_obj.name,
                "source_identifier": source_obj.identifier,
                "published_at": article.published_at,
                "discovered_at": article.discovered_at,
                "hunt_score": article.article_metadata.get("hunt_score")
                if article.article_metadata
                else None,
                "word_count": article.word_count,
                "summary": article.summary[:200] + "..." if article.summary and len(article.summary) > 200 else article.summary,
            }
            for article, source_obj in result.all()
        ]

        # Get unique sources for filter dropdown
        sources_query = select(Source.identifier, Source.name).order_by(Source.name)
        sources_result = await session.execute(sources_query)
        available_sources = [
            {"identifier": row[0], "name": row[1]} for row in sources_result.all()
        ]

        # Calculate pagination
        total_pages = (total_articles + per_page - 1) // per_page

    return templates.TemplateResponse(
        "articles.html",
        {
            "request": request,
            "articles": articles,
            "page": page,
            "per_page": per_page,
            "total_articles": total_articles,
            "total_pages": total_pages,
            "source": source,
            "min_hunt_score": min_hunt_score,
            "search": search,
            "sort_by": sort_by,
            "available_sources": available_sources,
        },
    )


@router.get("/articles/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int):
    """Article detail page"""
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

    return templates.TemplateResponse(
        "article_detail.html",
        {
            "request": request,
            "article": article,
            "source": source,
            "hunt_score": article.article_metadata.get("hunt_score")
            if article.article_metadata
            else None,
            "metadata": article.article_metadata or {},
        },
    )


@router.get("/sources", response_class=HTMLResponse)
async def sources_list(request: Request):
    """Sources management page"""
    async with get_async_session() as session:
        # Get database stats for sources
        result = await session.execute(select(Source).order_by(Source.name))
        db_sources = {s.identifier: s for s in result.scalars().all()}

    # Combine config with database stats
    sources_data = []
    for config in THREAT_INTEL_SOURCES:
        db_source = db_sources.get(config["identifier"])
        sources_data.append(
            {
                "identifier": config["identifier"],
                "name": config["name"],
                "url": config["url"],
                "rss_url": config.get("rss_url"),
                "active": config["active"],
                "check_frequency": config["check_frequency"],
                "has_rss": config.get("rss_url") is not None,
                "total_articles": db_source.total_articles if db_source else 0,
                "last_check": db_source.last_check if db_source else None,
                "last_success": db_source.last_success if db_source else None,
                "consecutive_failures": db_source.consecutive_failures if db_source else 0,
                "health_status": "healthy"
                if db_source and db_source.consecutive_failures == 0
                else "issues"
                if db_source and db_source.consecutive_failures > 0
                else "unknown",
            }
        )

    return templates.TemplateResponse(
        "sources.html",
        {
            "request": request,
            "sources": sources_data,
            "total_sources": len(sources_data),
            "active_sources": sum(1 for s in sources_data if s["active"]),
            "healthy_sources": sum(1 for s in sources_data if s["health_status"] == "healthy"),
        },
    )
