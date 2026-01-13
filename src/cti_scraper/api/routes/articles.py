"""Article routes with HTML annotation interface"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from ...db.base import get_async_session
from ...db.models import Article
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["Articles"])


# Dependency for FastAPI
async def get_db_session():
    """Dependency for getting async database session"""
    async with get_async_session() as session:
        yield session

# Setup templates
template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


@router.get("/{article_id}", response_class=HTMLResponse)
async def article_detail_page(
    request: Request,
    article_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Render article detail page with annotation interface.

    This page allows users to:
    - View article content
    - Select text for annotation
    - Label selections as "huntable" or "not_huntable"
    - View existing annotations
    """
    # Get article
    article = await session.get(Article, article_id)

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Render template
    return templates.TemplateResponse("article_detail.html", {
        "request": request,
        "article": article
    })


@router.get("/", response_class=HTMLResponse)
async def articles_list_page(
    request: Request,
    min_hunt_score: Optional[float] = 50.0,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Render articles list page for finding articles to annotate.

    Shows articles with high hunt scores that may benefit from annotation.
    """
    # Get articles ordered by hunt score (stored in article_metadata JSONB)
    # Note: hunt_score is in the article_metadata JSON field
    query = (
        select(Article)
        .order_by(Article.created_at.desc())
        .limit(limit)
    )

    result = await session.execute(query)
    articles = result.scalars().all()

    # Render template
    return templates.TemplateResponse("articles_list.html", {
        "request": request,
        "articles": articles,
        "min_hunt_score": min_hunt_score
    })
