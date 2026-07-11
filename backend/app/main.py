"""
NETRA — FastAPI Application Entry Point

Digital Public Safety Intelligence Platform
Detect · Investigate · Simulate
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, close_db
from app.routers import detect, graph, simulate, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize database tables
    if settings.DATABASE_URL:
        await init_db()
        logger.info("Database initialized")
    else:
        logger.warning("DATABASE_URL not set — running without database")

    yield

    # Cleanup
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Digital Public Safety Intelligence Platform — Detect · Investigate · Simulate",
        lifespan=lifespan,
    )

    # CORS — include deployed frontend URL if set
    cors_origins = list(settings.CORS_ORIGINS)
    if settings.FRONTEND_URL and settings.FRONTEND_URL not in cors_origins:
        cors_origins.append(settings.FRONTEND_URL)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(detect.router, prefix="/api/detect", tags=["Detect"])
    app.include_router(graph.router, prefix="/api/graph", tags=["Investigate"])
    app.include_router(simulate.router, prefix="/api/simulate", tags=["Simulate"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

    @app.get("/", tags=["Health"])
    async def health_check():
        return {
            "status": "online",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    @app.get("/api/config/mapbox-token", tags=["Config"])
    async def get_mapbox_token():
        """Serve Mapbox token to frontend (avoids exposing in client bundle)."""
        return {"token": settings.MAPBOX_TOKEN}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
