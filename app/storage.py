"""
Media storage service for Gojo Trip Planner.
Supports Cloudinary with automatic fallback to local disk storage.
"""
import logging
from pathlib import Path
from typing import Optional, Tuple
import aiofiles
import uuid
from app.config import settings

logger = logging.getLogger(__name__)

# Ensure local fallback directory exists
LOCAL_UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
LOCAL_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def is_cloudinary_configured() -> bool:
    """Check if Cloudinary credentials are provided."""
    if getattr(settings, "cloudinary_url", None):
        return True
    return bool(
        getattr(settings, "cloudinary_cloud_name", None)
        and getattr(settings, "cloudinary_api_key", None)
        and getattr(settings, "cloudinary_api_secret", None)
    )


def init_cloudinary():
    """Configure Cloudinary SDK if credentials exist."""
    if not is_cloudinary_configured():
        return False
    try:
        import cloudinary
        if getattr(settings, "cloudinary_url", None):
            cloudinary.config(cloudinary_url=settings.cloudinary_url)
        else:
            cloudinary.config(
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
                secure=True
            )
        return True
    except Exception as e:
        logger.warning(f"Failed to configure Cloudinary: {e}")
        return False


async def upload_file(
    content: bytes,
    filename: str,
    folder: str = "gojo",
    resource_type: str = "auto"
) -> Tuple[str, str]:
    """
    Upload a file either to Cloudinary (if configured) or local storage.
    Returns a tuple of (file_url, storage_id_or_path).
    """
    file_ext = Path(filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"

    if is_cloudinary_configured():
        try:
            import cloudinary.uploader
            init_cloudinary()
            import asyncio
            # Cloudinary uploader is sync, run in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: cloudinary.uploader.upload(
                    content,
                    folder=folder,
                    resource_type=resource_type,
                    public_id=Path(unique_filename).stem
                )
            )
            secure_url = result.get("secure_url") or result.get("url")
            public_id = result.get("public_id")
            return secure_url, public_id
        except Exception as e:
            logger.error(f"Cloudinary upload failed, falling back to local disk: {e}")

    # Fallback: Save to local uploads directory
    target_dir = LOCAL_UPLOADS_DIR / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    local_path = target_dir / unique_filename

    async with aiofiles.open(local_path, "wb") as f:
        await f.write(content)

    relative_url = f"/uploads/{folder}/{unique_filename}"
    return relative_url, str(local_path)


async def delete_file(storage_id_or_path: str, resource_type: str = "image"):
    """Delete a file from Cloudinary or local disk."""
    if not storage_id_or_path:
        return

    # Check if local file exists
    local_path = Path(storage_id_or_path)
    if local_path.is_absolute() and local_path.exists():
        try:
            local_path.unlink()
            return
        except Exception as e:
            logger.warning(f"Failed to delete local file {local_path}: {e}")

    # Try Cloudinary if it's a public_id
    if is_cloudinary_configured():
        try:
            import cloudinary.uploader
            init_cloudinary()
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: cloudinary.uploader.destroy(
                    storage_id_or_path,
                    resource_type=resource_type
                )
            )
        except Exception as e:
            logger.warning(f"Cloudinary deletion failed for {storage_id_or_path}: {e}")
