"""InkMemories FastAPI application."""

import logging
import sys
from pathlib import Path

# Allow running this file directly from backend/ directory
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import config, database
from backend.routers import pages, photos, tags


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"


app = FastAPI(title="InkMemories", version="1.0.0")

# Static files (CSS, JS, built frontend assets)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# HTML pages
app.include_router(pages.router)

# API routes
app.include_router(photos.router)
app.include_router(tags.router)


@app.on_event("startup")
def startup_event():
    """Initialize the database on startup."""
    database.init_db()


def run():
    """Run the application with uvicorn."""
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(
        "backend.main:app",
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
