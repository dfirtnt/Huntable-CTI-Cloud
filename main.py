#!/usr/bin/env python3
"""
CTI Scraper - Main Entry Point

Usage:
    python main.py

This starts the FastAPI application with uvicorn.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    import uvicorn
    from cti_scraper.config import get_settings

    settings = get_settings()

    uvicorn.run(
        "cti_scraper.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
