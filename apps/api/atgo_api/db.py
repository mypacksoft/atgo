from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def session_scope(
    tenant_id: int | None = None,
    bypass_rls: bool = False,
) -> AsyncIterator[AsyncSession]:
    """Open a session and bind tenant context for RLS.

    Use bypass_rls=True only for ADMS / system / admin operations that genuinely
    need cross-tenant access. Always prefer scoping by tenant_id.
    """
    async with SessionLocal() as session:
        # Set per-transaction context — RLS policies read these via current_setting()
        if bypass_rls:
            await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)").bindparams(tid=str(tenant_id))
            )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session WITHOUT tenant context.

    Routers that need tenant scope should depend on `tenant_session` instead
    (see deps.py).
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
