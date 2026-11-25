from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

_db_url = settings.database_url_resolved
_is_sqlite = _db_url.startswith("sqlite")

if _is_sqlite:
    # SQLite — use StaticPool (required for async SQLite in tests/dev)
    from sqlalchemy.pool import StaticPool
    engine = create_async_engine(
        _db_url,
        echo=settings.database_echo,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL — use a real connection pool
    engine = create_async_engine(
        _db_url,
        echo=settings.database_echo,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
    )

_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Verify the database connection. Schema changes belong in Alembic."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def get_session() -> AsyncSession:
    """FastAPI dependency: yields one DB session per request."""
    async with _session_factory() as session:
        yield session
