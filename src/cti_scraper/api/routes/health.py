"""Health check routes"""
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from cti_scraper.config import get_settings
from cti_scraper.db import get_async_session

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@router.get("/health/db")
async def database_health():
    """Database connectivity check"""
    try:
        async with get_async_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/health/ready")
async def readiness_check():
    """Kubernetes-style readiness check"""
    settings = get_settings()

    checks = {
        "database": False,
        "aws_config": False,
    }

    # Check database
    try:
        async with get_async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check AWS configuration
    if settings.aws_region and settings.aws_account_id:
        checks["aws_config"] = True

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }
