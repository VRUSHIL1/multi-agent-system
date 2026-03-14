import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()

# Lazy initialization of engine and session
_engine = None
_AsyncSessionLocal = None

def get_engine():
    global _engine
    if _engine is None:
        from app.common.settings import settings
        _engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    return _engine

def get_session_local():
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_local = get_session_local()
    async with session_local() as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        engine = get_engine()
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            logger.info("✅ Database connected successfully")
    except Exception as exc:
        logger.error("❌ Error connecting to database | error=%s", exc)
        raise exc

    # Load embedding model once at startup
    from app.services.pdf_service import get_pdf_service
    try:
        get_pdf_service()
        logger.info("✅ Embedding model loaded successfully")
    except Exception as exc:
        logger.warning("⚠️ Embedding model failed to load at startup | error=%s", exc)

    yield

    engine = get_engine()
    await engine.dispose()
    logger.info("🔌 Database connection closed")
