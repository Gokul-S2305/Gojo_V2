from fastapi import APIRouter, Request, Depends, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Photo
from app.auth_utils import get_current_user
from pathlib import Path
import aiofiles
import uuid
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# Uploads directory
UPLOADS_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

def get_trip_upload_dir(trip_id: int) -> Path:
    """Get or create upload directory for a trip."""
    trip_dir = UPLOADS_DIR / str(trip_id)
    trip_dir.mkdir(exist_ok=True)
    return trip_dir

@router.get("/trip/{trip_id}/gallery", response_class=HTMLResponse)
async def trip_gallery(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    # Get trip
    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()
    
    if not trip:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    
    # Check if user is member
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    
    # Get all photos for this trip
    photos_statement = select(Photo).where(Photo.trip_id == trip_id).order_by(Photo.uploaded_at.desc())
    photos_result = await session.execute(photos_statement)
    photos = photos_result.scalars().all()
    
    # Load user relationship for each photo
    for photo in photos:
        await session.refresh(photo, ["user"])
    
    return templates.TemplateResponse("gallery.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "photos": photos
    })

@router.post("/trip/{trip_id}/upload")
async def upload_photo(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    photo: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    # Verify user is member of trip
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    
    # Validate file type
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".webm"}
    file_ext = Path(photo.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        return RedirectResponse(f"/trip/{trip_id}/gallery?error=Invalid file type", status_code=status.HTTP_302_FOUND)
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    trip_dir = get_trip_upload_dir(trip_id)
    file_path = trip_dir / unique_filename
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await photo.read()
        await f.write(content)
    
    # Create photo record
    new_photo = Photo(
        trip_id=trip_id,
        user_id=user.id,
        filename=unique_filename,
        media_type="video" if file_ext in {".mp4", ".mov", ".webm"} else "image"
    )
    session.add(new_photo)
    await session.commit()
    
    return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)

@router.get("/uploads/{trip_id}/{filename}")
async def get_photo(trip_id: int, filename: str):
    """Serve uploaded photos."""
    file_path = UPLOADS_DIR / str(trip_id) / filename
    
    if not file_path.exists():
        return RedirectResponse("/static/placeholder.jpg", status_code=status.HTTP_302_FOUND)
    
    return FileResponse(file_path)

@router.post("/trip/{trip_id}/photo/{photo_id}/delete")
async def delete_photo(
    request: Request,
    trip_id: int,
    photo_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    # Get photo
    photo_statement = select(Photo).where(Photo.id == photo_id, Photo.trip_id == trip_id)
    photo_result = await session.execute(photo_statement)
    photo = photo_result.scalar_one_or_none()
    
    if not photo:
        return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)
    
    # Only allow user who uploaded photo to delete it
    if photo.user_id != user.id:
        return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)
    
    # Delete file
    file_path = UPLOADS_DIR / str(trip_id) / photo.filename
    if file_path.exists():
        file_path.unlink()
    
    # Delete record
    await session.delete(photo)
    await session.commit()
    
    return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)
