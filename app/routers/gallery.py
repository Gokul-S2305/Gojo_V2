from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Photo
from app.auth_utils import get_current_user
from app.config import settings
from app.storage import upload_file, delete_file
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

MAX_UPLOAD_BYTES = settings.max_upload_size  # 10MB default
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm"}
ALLOWED_EXT = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT


@router.get("/gallery", response_class=HTMLResponse)
async def gallery_root(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    statement = (
        select(Trip)
        .join(TripUserLink)
        .where(TripUserLink.user_id == user.id)
        .order_by(Trip.id.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    trip = result.scalar_one_or_none()

    if trip:
        return await trip_gallery(request, trip.id, user, session)

    return templates.TemplateResponse("gallery.html", {
        "request": request, "user": user, "trip": None, "photos": []
    })


@router.get("/trip/{trip_id}/gallery", response_class=HTMLResponse)
async def trip_gallery(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    current_link = link_result.scalar_one_or_none()

    if not current_link:
        raise HTTPException(status_code=404, detail="Trip not found")

    is_organizer = current_link.role == "organizer"

    # Get photos with user info via JOIN
    photos_statement = (
        select(Photo, User)
        .join(User, Photo.user_id == User.id)
        .where(Photo.trip_id == trip_id)
        .order_by(Photo.uploaded_at.desc())
    )
    photos_result = await session.execute(photos_statement)
    photos_data = photos_result.all()

    photos = [
        {
            "id": p.id,
            "filename": p.filename,
            "url": p.url or f"/uploads/trips/{trip_id}/{p.filename}",
            "media_type": p.media_type,
            "caption": p.caption,
            "uploaded_at": p.uploaded_at,
            "user_id": p.user_id,
            "user_name": u.full_name or u.email,
            "trip_id": trip_id,
            "can_delete": (p.user_id == user.id or is_organizer)
        }
        for p, u in photos_data
    ]

    return templates.TemplateResponse("gallery.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "photos": photos,
        "is_organizer": is_organizer,
    })


@router.post("/trip/{trip_id}/upload")
async def upload_photo(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    photo: UploadFile = File(...),
    caption: str = Form(None),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Trip not found")

    file_ext = Path(photo.filename).suffix.lower()
    if file_ext not in ALLOWED_EXT:
        return RedirectResponse(
            f"/trip/{trip_id}/gallery?error=Invalid+file+type",
            status_code=status.HTTP_302_FOUND
        )

    content = await photo.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        return RedirectResponse(
            f"/trip/{trip_id}/gallery?error=File+too+large+(max+10MB)",
            status_code=status.HTTP_302_FOUND
        )

    # Upload to Cloudinary or local disk
    media_type = "video" if file_ext in ALLOWED_VIDEO_EXT else "image"
    file_url, storage_id = await upload_file(
        content=content,
        filename=photo.filename,
        folder=f"trips/{trip_id}",
        resource_type=media_type
    )

    new_photo = Photo(
        trip_id=trip_id,
        user_id=user.id,
        filename=Path(file_url).name,
        url=file_url,
        storage_id=storage_id,
        media_type=media_type,
        caption=caption.strip() if caption else None,
    )
    session.add(new_photo)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}/gallery?msg=Photo+uploaded", status_code=status.HTTP_302_FOUND)


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

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    current_link = link_result.scalar_one_or_none()

    if not current_link:
        raise HTTPException(status_code=404, detail="Trip not found")

    photo_statement = select(Photo).where(Photo.id == photo_id, Photo.trip_id == trip_id)
    photo_result = await session.execute(photo_statement)
    photo = photo_result.scalar_one_or_none()

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    if photo.user_id != user.id and current_link.role != "organizer":
        raise HTTPException(status_code=403, detail="Permission denied to delete photo")

    # Delete from Cloudinary or local disk
    await delete_file(photo.storage_id or photo.url, resource_type=photo.media_type)

    await session.delete(photo)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}/gallery?msg=Photo+deleted", status_code=status.HTTP_302_FOUND)
