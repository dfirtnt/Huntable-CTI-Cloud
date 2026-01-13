"""API routes"""
from .cost import router as cost_router
from .health import router as health_router
from .ml import router as ml_router
from .scraper import router as scraper_router

__all__ = ["cost_router", "health_router", "ml_router", "scraper_router"]
