from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# Create async engine with config-based settings
engine = create_async_engine(
    settings.database_url_resolved, 
    echo=settings.database_echo,  # Only echo in development
    future=True,
    pool_pre_ping=True  # Verify connections before using
)

async def init_db():
    async with engine.begin() as conn:
        # Import models to ensure they are registered with SQLModel.metadata
        # This prevents "table not found" issues if models weren't imported yet
        from app import models
        
        # Create all tables
        await conn.run_sync(SQLModel.metadata.create_all)
        
        # Auto-migration: Add columns if they don't exist
        # SQLite does not support "IF NOT EXISTS" for ADD COLUMN, so we wrap in try-except
        migration_statements = [
            "ALTER TABLE trip ADD COLUMN start_location TEXT;",
            "ALTER TABLE trip ADD COLUMN estimated_budget FLOAT;",
            "ALTER TABLE tripuserlink ADD COLUMN role TEXT DEFAULT 'member';",
            "ALTER TABLE photo ADD COLUMN media_type TEXT DEFAULT 'image';"
        ]
        
        for statement in migration_statements:
            try:
                await conn.execute(text(statement))
            except Exception as e:
                # Ignore "duplicate column" error, but log others if significant
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    continue
                logger.warning(f"Migration statement ignored: {statement} - Error: {e}")

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
