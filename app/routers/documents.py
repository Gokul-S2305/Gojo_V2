from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Document
from app.auth_utils import get_current_user
from app.config import settings
from app.storage import upload_file, delete_file, LOCAL_UPLOADS_DIR, signed_download_url
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

DOC_TYPE_ICONS = {
    "hotel": "building",
    "flight": "plane",
    "bus": "bus",
    "train": "train",
    "car": "car",
    "other": "file-text",
}

ALLOWED_DOC_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


@router.get("/trip/{trip_id}/documents", response_class=HTMLResponse)
async def trip_documents(
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

    # Get documents with user info via JOIN
    docs_statement = (
        select(Document, User)
        .join(User, Document.user_id == User.id)
        .where(Document.trip_id == trip_id)
        .order_by(Document.created_at.desc())
    )
    docs_result = await session.execute(docs_statement)
    docs_data = docs_result.all()

    documents = [
        {
            "id": d.id,
            "doc_type": d.doc_type,
            "icon": DOC_TYPE_ICONS.get(d.doc_type, "file-text"),
            "title": d.title,
            "vendor": d.vendor,
            "booking_ref": d.booking_ref,
            "date_from": d.date_from,
            "date_to": d.date_to,
            "from_location": d.from_location,
            "to_location": d.to_location,
            "notes": d.notes,
            "file_url": d.file_url or (f"/uploads/docs/{trip_id}/{d.file_path}" if d.file_path else None),
            "file_path": d.file_path,
            "created_at": d.created_at,
            "user_id": d.user_id,
            "user_name": u.full_name or u.email,
            "can_delete": (d.user_id == user.id or is_organizer),
        }
        for d, u in docs_data
    ]

    return templates.TemplateResponse("documents.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "documents": documents,
        "doc_types": list(DOC_TYPE_ICONS.keys()),
        "is_organizer": is_organizer,
    })


@router.post("/trip/{trip_id}/documents/add")
async def add_document(
    request: Request,
    trip_id: int,
    doc_type: str = Form(...),
    title: str = Form(...),
    vendor: str = Form(None),
    booking_ref: str = Form(None),
    date_from: str = Form(None),
    date_to: str = Form(None),
    from_location: str = Form(None),
    to_location: str = Form(None),
    notes: str = Form(None),
    attachment: UploadFile = File(None),
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
    if not link_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Trip not found")

    file_url = None
    storage_id = None
    stored_filename = None

    if attachment and attachment.filename:
        file_ext = Path(attachment.filename).suffix.lower()
        if file_ext not in ALLOWED_DOC_EXTENSIONS:
            return RedirectResponse(
                f"/trip/{trip_id}/documents?error=Invalid+file+type",
                status_code=status.HTTP_302_FOUND
            )
        content = await attachment.read(settings.max_upload_size + 1)
        if len(content) > settings.max_upload_size:
            return RedirectResponse(
                f"/trip/{trip_id}/documents?error=File+too+large",
                status_code=status.HTTP_302_FOUND
            )
        file_url, storage_id = await upload_file(
            content=content,
            filename=attachment.filename,
            folder=f"docs/{trip_id}",
            resource_type="raw"
        )
        stored_filename = Path(file_url).name

    new_doc = Document(
        trip_id=trip_id,
        user_id=user.id,
        doc_type=doc_type,
        title=title.strip(),
        vendor=vendor.strip() if vendor else None,
        booking_ref=booking_ref.strip() if booking_ref else None,
        date_from=date_from or None,
        date_to=date_to or None,
        from_location=from_location.strip() if from_location else None,
        to_location=to_location.strip() if to_location else None,
        notes=notes.strip() if notes else None,
        file_path=stored_filename,
        file_url=file_url,
        storage_id=storage_id,
    )
    session.add(new_doc)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}/documents?msg=Document+added", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/documents/{doc_id}/delete")
async def delete_document(
    trip_id: int,
    doc_id: int,
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

    doc_statement = select(Document).where(Document.id == doc_id, Document.trip_id == trip_id)
    doc_result = await session.execute(doc_statement)
    doc = doc_result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.user_id != user.id and current_link.role != "organizer":
        raise HTTPException(status_code=403, detail="Permission denied to delete document")

    if doc.storage_id or doc.file_url:
        await delete_file(doc.storage_id or doc.file_url, resource_type="raw")

    await session.delete(doc)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}/documents?msg=Document+deleted", status_code=status.HTTP_302_FOUND)


@router.get("/trip/{trip_id}/documents/{doc_id}/download")
async def download_document(
    trip_id: int,
    doc_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    # Secure membership check
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Trip not found")

    doc_statement = select(Document).where(Document.id == doc_id, Document.trip_id == trip_id)
    doc_result = await session.execute(doc_statement)
    doc = doc_result.scalar_one_or_none()

    if not doc or (not doc.file_url and not doc.file_path):
        raise HTTPException(status_code=404, detail="Attachment not found")

    if doc.storage_id:
        try:
            signed_url = signed_download_url(doc.storage_id, resource_type="raw")
            return RedirectResponse(signed_url)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

    # Local fallback file
    file_path = LOCAL_UPLOADS_DIR / f"docs/{trip_id}" / (doc.file_path or "")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Attachment file not found on disk")

    return FileResponse(file_path, filename=f"{doc.title}{file_path.suffix}")
