from fastapi import APIRouter, Request, Depends, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Photo
from app.auth_utils import get_current_user
from app.config import settings
from pathlib import Path
import aiofiles
import uuid

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

UPLOADS_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

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

    statement = select(Trip).join(TripUserLink).where(
        TripUserLink.user_id == user.id
    ).order_by(Trip.id.desc()).limit(1)
    result = await session.execute(statement)
    trip = result.scalar_one_or_none()

    if trip:
        return await trip_gallery(request, trip.id, user, session)

    return templates.TemplateResponse("gallery.html", {
        "request": request, "user": user, "trip": None, "photos": []
    })


def get_trip_upload_dir(trip_id: int) -> Path:
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

    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()

    if not trip:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    # Get photos with user info via JOIN (fixes N+1)
    from app.models import User as UserModel
    photos_statement = select(Photo, UserModel).join(
        UserModel, Photo.user_id == UserModel.id
    ).where(Photo.trip_id == trip_id).order_by(Photo.uploaded_at.desc())
    photos_result = await session.execute(photos_statement)
    photos_data = photos_result.all()

    photos = [
        {
            "id": p.id,
            "filename": p.filename,
            "media_type": p.media_type,
            "caption": p.caption,
            "uploaded_at": p.uploaded_at,
            "user_id": p.user_id,
            "user_name": u.full_name or u.email,
            "trip_id": trip_id,
        }
        for p, u in photos_data
    ]

    return templates.TemplateResponse("gallery.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "photos": photos,
    })


@router.post("/trip/{trip_id}/upload")
async def upload_photo(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    photo: UploadFile = File(...),
    caption: str = None,
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
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    file_ext = Path(photo.filename).suffix.lower()
    if file_ext not in ALLOWED_EXT:
        return RedirectResponse(
            f"/trip/{trip_id}/gallery?error=Invalid+file+type",
            status_code=status.HTTP_302_FOUND
        )

    # Read content with size check (Fix: validate file size before saving)
    content = await photo.read()
    if len(content) > MAX_UPLOAD_BYTES:
        return RedirectResponse(
            f"/trip/{trip_id}/gallery?error=File+too+large+(max+10MB)",
            status_code=status.HTTP_302_FOUND
        )

    unique_filename = f"{uuid.uuid4()}{file_ext}"
    trip_dir = get_trip_upload_dir(trip_id)
    file_path = trip_dir / unique_filename

    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

    trip_result = await session.execute(select(Trip).where(Trip.id == trip_id))
    trip = trip_result.scalar_one_or_none()

    new_photo = Photo(
        trip_id=trip_id,
        user_id=user.id,
        filename=unique_filename,
        media_type="video" if file_ext in ALLOWED_VIDEO_EXT else "image",
        caption=caption,
    )
    session.add(new_photo)
    await session.commit()

    # Google Drive Sync
    if trip and user.drive_connected and trip.drive_folder_id:
        google_access_token = request.session.get('google_access_token')
        if google_access_token:
            try:
                from app.drive_service import get_drive_service, upload_file_to_drive
                service = get_drive_service(google_access_token)
                await upload_file_to_drive(service, file_path, trip.drive_folder_id, new_photo.media_type)
            except Exception as e:
                print(f"Drive upload failed: {e}")

    return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)


@router.get("/uploads/{trip_id}/{filename}")
async def get_photo(trip_id: int, filename: str):
    """Serve uploaded photos."""
    file_path = UPLOADS_DIR / str(trip_id) / filename
    if not file_path.exists():
        return RedirectResponse("/static/images/placeholder.jpg", status_code=status.HTTP_302_FOUND)
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

    photo_statement = select(Photo).where(Photo.id == photo_id, Photo.trip_id == trip_id)
    photo_result = await session.execute(photo_statement)
    photo = photo_result.scalar_one_or_none()

    if not photo:
        return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)

    if photo.user_id != user.id:
        return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)

    file_path = UPLOADS_DIR / str(trip_id) / photo.filename
    if file_path.exists():
        file_path.unlink()

    await session.delete(photo)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}/gallery", status_code=status.HTTP_302_FOUND)
