from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Document
from app.auth_utils import get_current_user
from app.config import settings
from pathlib import Path
import aiofiles
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

DOCS_DIR = Path(__file__).parent.parent.parent / "uploads" / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

DOC_TYPE_ICONS = {
    "hotel": "🏨",
    "flight": "✈️",
    "bus": "🚌",
    "train": "🚂",
    "car": "🚗",
    "other": "📄",
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
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    # Get documents with user info via JOIN
    from app.models import User as UserModel
    docs_statement = select(Document, UserModel).join(
        UserModel, Document.user_id == UserModel.id
    ).where(Document.trip_id == trip_id).order_by(Document.created_at.desc())
    docs_result = await session.execute(docs_statement)
    docs_data = docs_result.all()

    documents = [
        {
            "id": d.id,
            "doc_type": d.doc_type,
            "icon": DOC_TYPE_ICONS.get(d.doc_type, "📄"),
            "title": d.title,
            "vendor": d.vendor,
            "booking_ref": d.booking_ref,
            "date_from": d.date_from,
            "date_to": d.date_to,
            "from_location": d.from_location,
            "to_location": d.to_location,
            "notes": d.notes,
            "file_path": d.file_path,
            "created_at": d.created_at,
            "user_id": d.user_id,
            "user_name": u.full_name or u.email,
        }
        for d, u in docs_data
    ]

    return templates.TemplateResponse("documents.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "documents": documents,
        "doc_types": list(DOC_TYPE_ICONS.keys()),
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
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    file_path = None
    if attachment and attachment.filename:
        file_ext = Path(attachment.filename).suffix.lower()
        if file_ext in ALLOWED_DOC_EXTENSIONS:
            content = await attachment.read()
            if len(content) <= settings.max_upload_size:
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                dest_path = DOCS_DIR / unique_filename
                async with aiofiles.open(dest_path, 'wb') as f:
                    await f.write(content)
                file_path = unique_filename

    new_doc = Document(
        trip_id=trip_id,
        user_id=user.id,
        doc_type=doc_type,
        title=title,
        vendor=vendor,
        booking_ref=booking_ref,
        date_from=date_from or None,
        date_to=date_to or None,
        from_location=from_location,
        to_location=to_location,
        notes=notes,
        file_path=file_path,
    )
    session.add(new_doc)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}/documents", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/documents/{doc_id}/delete")
async def delete_document(
    trip_id: int,
    doc_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    doc_statement = select(Document).where(Document.id == doc_id, Document.trip_id == trip_id)
    doc_result = await session.execute(doc_statement)
    doc = doc_result.scalar_one_or_none()

    if not doc or doc.user_id != user.id:
        return RedirectResponse(f"/trip/{trip_id}/documents", status_code=status.HTTP_302_FOUND)

    if doc.file_path:
        file_path = DOCS_DIR / doc.file_path
        if file_path.exists():
            file_path.unlink()

    await session.delete(doc)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}/documents", status_code=status.HTTP_302_FOUND)


@router.get("/trip/{trip_id}/documents/{doc_id}/download")
async def download_document(
    trip_id: int,
    doc_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    doc_statement = select(Document).where(Document.id == doc_id, Document.trip_id == trip_id)
    doc_result = await session.execute(doc_statement)
    doc = doc_result.scalar_one_or_none()

    if not doc or not doc.file_path:
        return JSONResponse({"error": "File not found"}, status_code=404)

    file_path = DOCS_DIR / doc.file_path
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)

    return FileResponse(file_path, filename=f"{doc.title}{Path(doc.file_path).suffix}")
