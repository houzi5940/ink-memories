"""InkMemories FastAPI application."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Allow running this file directly from backend/ directory
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import config, database
from backend import analyzer
from backend.routers import pages, photos, tags


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB + start/stop the analysis worker."""
    # ---- startup ----
    database.init_db()
    # 启动恢复：上次中断遗留的 analyzing 重置为 pending
    recovered = database.reset_stale_analyzing()
    if recovered:
        logging.getLogger(__name__).info(f"恢复 {recovered} 张中断的待分析照片")
    # 起常驻分析 worker，并唤醒一次以续跑历史 pending
    worker_task = asyncio.create_task(analyzer.analysis_worker())
    app.state.worker_task = worker_task
    analyzer.signal_worker()
    try:
        yield
    finally:
        # ---- shutdown ----
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="InkMemories", version="1.0.0", lifespan=lifespan)

# Static files (CSS, JS, built frontend assets)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# HTML pages
app.include_router(pages.router)

# API routes
app.include_router(photos.router)
app.include_router(tags.router)



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
