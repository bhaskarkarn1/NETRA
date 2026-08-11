"""
NETRA — FastAPI Application Entry Point

Digital Public Safety Intelligence Platform
Detect · Investigate · Simulate
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, close_db
from app.routers import detect, graph, simulate, dashboard, disrupt
from app.routers.evaluation import eval_router, intel_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Background task handle for Neon keep-alive
_keepalive_task: asyncio.Task | None = None


async def _neon_keepalive_loop():
    """Ping Neon DB every 4 minutes to prevent serverless compute from sleeping.

    Neon free tier suspends compute after 5 minutes of inactivity.
    A lightweight SELECT 1 keeps the connection warm and avoids
    the 3-5 second cold start penalty on the next real request.
    """
    from app.database import get_engine
    from sqlalchemy import text

    while True:
        try:
            await asyncio.sleep(240)  # 4 minutes
            engine = await get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.debug("Neon keep-alive ping OK")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Neon keep-alive ping failed: {e}")


async def _prewarm_dashboard_cache():
    """Pre-warm the dashboard cache on startup so the first visitor
    gets instant data instead of waiting for 12+ cold DB queries."""
    from app.database import get_session_factory
    try:
        factory = await get_session_factory()
        async with factory() as session:
            try:
                # Import the endpoint functions and call them directly
                from app.routers.dashboard import get_metrics, get_threat_feed, get_analytics
                await get_metrics(db=session)
                await get_threat_feed(limit=15, db=session)
                await get_analytics(db=session)
                await session.commit()
                logger.info("Dashboard cache pre-warmed successfully")
            except Exception:
                await session.rollback()
                raise
    except Exception as e:
        logger.warning(f"Dashboard cache pre-warm failed (non-critical): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global _keepalive_task
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize database tables
    if settings.DATABASE_URL:
        await init_db()
        logger.info("Database initialized")

        # Start Neon keep-alive background task
        _keepalive_task = asyncio.create_task(_neon_keepalive_loop())
        logger.info("Neon keep-alive task started (ping every 4 min)")

        # Pre-warm dashboard cache in background (don't block startup)
        asyncio.create_task(_prewarm_dashboard_cache())
    else:
        logger.warning("DATABASE_URL not set — running without database")

    yield

    # Cleanup
    if _keepalive_task:
        _keepalive_task.cancel()
        try:
            await _keepalive_task
        except asyncio.CancelledError:
            pass
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

    # CORS — include deployed frontend URL + all Vercel preview domains
    cors_origins = list(settings.CORS_ORIGINS)
    if settings.FRONTEND_URL and settings.FRONTEND_URL not in cors_origins:
        cors_origins.append(settings.FRONTEND_URL)

    # Always allow Vercel deployment domains
    vercel_domains = [
        "https://netra-dusky.vercel.app",
        "https://netra.vercel.app",
    ]
    for domain in vercel_domains:
        if domain not in cors_origins:
            cors_origins.append(domain)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"https://netra.*\.vercel\.app",  # All Vercel preview URLs
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(detect.router, prefix="/api/detect", tags=["Detect"])
    app.include_router(graph.router, prefix="/api/graph", tags=["Investigate"])
    app.include_router(simulate.router, prefix="/api/simulate", tags=["Simulate"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(disrupt.router, prefix="/api/disrupt", tags=["Disrupt"])
    app.include_router(eval_router, prefix="/api/evaluation", tags=["Evaluation"])
    app.include_router(intel_router, prefix="/api/intelligence", tags=["Intelligence"])

    @app.get("/", tags=["Health"])
    async def health_check():
        return {
            "status": "online",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    @app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"])
    async def health_deep():
        """Health check with DB connectivity validation.

        Designed for UptimeRobot monitoring — pinging this endpoint
        every 5 minutes keeps both Railway (container) and Neon
        (serverless Postgres) warm, eliminating cold start delays.
        """
        from sqlalchemy import text as sa_text
        from app.database import get_engine

        db_status = "disconnected"
        try:
            engine = await get_engine()
            async with engine.connect() as conn:
                await conn.execute(sa_text("SELECT 1"))
            db_status = "connected"
        except Exception as e:
            logger.warning(f"Health check DB ping failed: {e}")

        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "database": db_status,
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
