from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.core.config import settings
from app.db.database import AsyncSessionLocal, create_tables
from app.services.cache import cache_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    return {
        "message": "AI Q&A API is running"
    }


@app.get("/health")
async def health():
    postgres_status = "healthy"
    redis_status = "healthy"

    # Check PostgreSQL
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        postgres_status = "unhealthy"

    # Check Redis
    try:
        await cache_service.redis.ping()
    except Exception:
        redis_status = "unhealthy"

    overall_status = (
        "healthy"
        if postgres_status == "healthy"
        and redis_status == "healthy"
        else "unhealthy"
    )

    return {
        "status": overall_status,
        "dependencies": {
            "postgres": postgres_status,
            "redis": redis_status,
        },
    }


Instrumentator().instrument(app).expose(app)