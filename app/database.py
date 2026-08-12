from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings
from sqlalchemy import text
import logging
import asyncio

logger = logging.getLogger(__name__)

_db_url = settings.database_url_resolved
_is_sqlite = _db_url.startswith("sqlite")

if _is_sqlite:
    # SQLite doesn't support connection pooling
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


# Single shared session factory — created once, reused on every request
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Initialize database tables and run migrations. Called at startup — AWAITED (not fire-and-forget)."""
    max_retries = 30
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                # Import models to register them with SQLModel.metadata
                from app import models  # noqa: F401

                # Create all tables
                await conn.run_sync(SQLModel.metadata.create_all)

                # Auto-migration: Add columns if they don't exist
                # PostgreSQL uses "column ... of relation ... already exists"
                # SQLite uses "duplicate column name"
                migration_statements = [
                    "ALTER TABLE trip ADD COLUMN start_location TEXT;",
                    "ALTER TABLE trip ADD COLUMN estimated_budget FLOAT;",
                    "ALTER TABLE trip ADD COLUMN notes TEXT;",
                    "ALTER TABLE tripuserlink ADD COLUMN role TEXT DEFAULT 'member';",
                    "ALTER TABLE photo ADD COLUMN media_type TEXT DEFAULT 'image';",
                    "ALTER TABLE photo ADD COLUMN caption TEXT;",
                    "ALTER TABLE expense ADD COLUMN category TEXT DEFAULT 'Other';",
                    "ALTER TABLE itineraryitem ADD COLUMN category TEXT DEFAULT 'Activity';",
                ]

                for statement in migration_statements:
                    try:
                        await conn.execute(text(statement))
                    except Exception as e:
                        err_str = str(e).lower()
                        # Silently skip "column already exists" errors from both SQLite and PostgreSQL
                        if (
                            "duplicate column name" in err_str
                            or "already exists" in err_str
                            or "column" in err_str and "of relation" in err_str
                        ):
                            continue
                        logger.warning(f"Migration statement skipped: {statement!r} — {e}")

            logger.info("Database initialized successfully.")
            return  # success — exit immediately

        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(10)
            else:
                raise RuntimeError(f"Database failed to initialize after {max_retries} attempts: {e}") from e


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields a database session per request."""
    async with async_session_factory() as session:
        yield session
