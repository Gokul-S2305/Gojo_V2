"""
Centralized configuration management for Gojo Trip Planner.
Uses environment variables for secure configuration.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "Gojo Trip Planner"
    environment: str = "development"
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./gojo.db"
    database_echo: bool = False  # Disabled by default for security
    
    # File Upload
    max_upload_size: int = 10485760  # 10MB
    allowed_extensions: str = "jpg,jpeg,png,gif,webp"
    upload_dir: str = "uploads"
    
    # Email (for future use)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@gojotrips.com"
    
    # Frontend
    site_url: str = "http://127.0.0.1:8000"

    # AI Integration
    gemini_api_key: str = ""  # Loaded from .env
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def database_url_resolved(self) -> str:
        """
        Fixes the database URL scheme for SQLAlchemy async engine.
        Render provides 'postgresql://' but async engine needs 'postgresql+asyncpg://'
        """
        url = self.database_url
        if url and url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url and url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Get list of allowed file extensions."""
        return [ext.strip() for ext in self.allowed_extensions.split(",")]
    
    @property
    def upload_path(self) -> Path:
        """Get upload directory path."""
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
