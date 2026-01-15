from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

from sqlalchemy import text

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
        # This fixes the "no such column" errors
        await conn.execute(text("ALTER TABLE trip ADD COLUMN IF NOT EXISTS start_location TEXT;"))
        await conn.execute(text("ALTER TABLE trip ADD COLUMN IF NOT EXISTS estimated_budget FLOAT;"))
        await conn.execute(text("ALTER TABLE tripuserlink ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'member';"))
        await conn.execute(text("ALTER TABLE photo ADD COLUMN IF NOT EXISTS media_type TEXT DEFAULT 'image';"))

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
