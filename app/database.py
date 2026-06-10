from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from sqlalchemy import text
import logging
import asyncio
import socket

logger = logging.getLogger(__name__)

# Create async engine with config-based settings
engine = create_async_engine(
    settings.database_url_resolved,
    echo=settings.database_echo,
    future=True,
    pool_pre_ping=True
)

async def init_db():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                # Import models to ensure they are registered with SQLModel.metadata
                from app import models  # noqa: F401

                # Create all tables
                await conn.run_sync(SQLModel.metadata.create_all)

                # Auto-migration: Add columns if they don't exist
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
                        if "duplicate column name" in err_str or "already exists" in err_str:
                            continue
                        logger.warning(f"Migration statement ignored: {statement} - Error: {e}")
            
            logger.info("Database initialized successfully.")
            break
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
            else:
                raise e



async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
