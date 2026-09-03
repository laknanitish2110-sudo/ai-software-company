import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import validate_sandbox_config, validate_jwt_config
from app.core.database import init_db, get_pg_pool
from app.api.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_sandbox_config()
    validate_jwt_config()
    await init_db()
    yield
    # Graceful shutdown
    try:
        pool = await get_pg_pool()
        if pool is not None:
            await pool.close()
            logger.info("PostgreSQL connection pool closed.")
    except Exception as e:
        logger.warning(f"Error closing pg pool: {e}")
    try:
        from app.services.redis_coordinator import redis_coordinator
        await redis_coordinator.close()
    except Exception as e:
        logger.warning(f"Error closing Redis: {e}")


app = FastAPI(
    title="AI Software Company",
    description="Your personal AI engineering team",
    version="0.1.0",
    lifespan=lifespan,
)

allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]

frontend_url = os.getenv("FRONTEND_URL", "")
if frontend_url:
    allowed_origins.append(frontend_url.rstrip("/"))

cors_kwargs: dict = {
    "allow_origins": allowed_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if not frontend_url:
    cors_kwargs["allow_origin_regex"] = r"https://.*\.(vercel\.app|onrender\.com)"

app.add_middleware(CORSMiddleware, **cors_kwargs)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"name": "AI Software Company", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    status = {"status": "ok", "db": "unknown", "redis": "unknown"}
    code = 200

    # Check database
    try:
        from app.core.database import get_db
        db = await get_db()
        try:
            await db.execute("SELECT 1")
            status["db"] = "ok"
        finally:
            await db.close()
    except Exception as e:
        status["db"] = f"error: {e}"
        status["status"] = "degraded"
        code = 503

    # Check Redis
    try:
        from app.services.redis_coordinator import redis_coordinator
        if await redis_coordinator.ping():
            status["redis"] = "ok"
        else:
            status["redis"] = "unavailable"
            status["status"] = "degraded"
    except Exception as e:
        status["redis"] = f"error: {e}"
        status["status"] = "degraded"

    from fastapi.responses import JSONResponse
    return JSONResponse(content=status, status_code=code)
