"""FastAPI application factory"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cti_scraper.config import get_settings
from cti_scraper.db import close_db, init_db

from .routes import cost_router, health_router, ml_router, scraper_router
from .routes.articles import router as articles_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting CTI Scraper application...")
    settings = get_settings()
    logger.info(f"Environment: {settings.app_env}")

    # Initialize database (only in development, use Alembic in production)
    if settings.is_development:
        await init_db()
        logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down CTI Scraper application...")
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    settings = get_settings()

    app = FastAPI(
        title="CTI Scraper",
        description="Threat Intelligence Aggregation and Analysis Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(cost_router, prefix="/costs", tags=["Cost Monitoring"])
    app.include_router(scraper_router, prefix="/scraper", tags=["Scraper"])
    app.include_router(ml_router, tags=["ML"])
    app.include_router(articles_router, tags=["Articles"])

    # Mount static files (when directory exists)
    # app.mount("/static", StaticFiles(directory="src/cti_scraper/static"), name="static")

    logger.info("FastAPI application created successfully")
    return app


# Create application instance
app = create_app()
