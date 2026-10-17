import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.database import init_db, get_db
from app.api.auth import router as auth_router
from app.api.teams import router as teams_router
from app.api.work_items import router as work_items_router
from app.services.outbox_worker import start_outbox_worker_loop

# Configure structured logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("newtonite_ops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database schemas and launch async outbox worker."""
    logger.info("Initializing database tables...")
    await init_db()
    logger.info("Database initialized successfully.")

    # Launch background outbox worker
    worker_task = asyncio.create_task(start_outbox_worker_loop())

    yield

    # Clean shutdown
    logger.info("Shutting down background outbox worker...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("Outbox worker shut down cleanly.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise Work Item Management with Concurrency Control, Optimistic Locking, State Machine & Audit Trails",
    lifespan=lifespan,
)

# Enable CORS for frontend development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth_router)
app.include_router(teams_router)
app.include_router(work_items_router)


@app.get("/api/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint validating API and database connectivity."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
