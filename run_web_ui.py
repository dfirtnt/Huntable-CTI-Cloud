"""Run FastAPI web UI locally"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    import uvicorn
    from cti_scraper.api.app import app

    print("\n" + "="*80)
    print("CTI Scraper Web UI")
    print("="*80)
    print("\nStarting server at: http://localhost:8000")
    print("\nAvailable endpoints:")
    print("  - http://localhost:8000/articles           - Browse articles")
    print("  - http://localhost:8000/articles/{id}      - View article details")
    print("  - http://localhost:8000/docs               - API documentation")
    print("\nPress CTRL+C to stop\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
