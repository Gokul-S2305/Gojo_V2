from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Message
from app.auth_utils import get_current_user
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/trip/{trip_id}/chat", response_class=HTMLResponse)
async def trip_chat(
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
    
    # Get all messages for this trip
    messages_statement = select(Message).where(Message.trip_id == trip_id).order_by(Message.timestamp.asc())
    messages_result = await session.execute(messages_statement)
    messages = messages_result.scalars().all()
    
    # Load user relationship for each message
    for message in messages:
        await session.refresh(message, ["user"])
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "messages": messages
    })

@router.post("/trip/{trip_id}/message")
async def send_message(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    content: str = Form(...),
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
    
    # Create message
    new_message = Message(
        trip_id=trip_id,
        user_id=user.id,
        content=content.strip()
    )
    session.add(new_message)
    await session.commit()
    
    return RedirectResponse(f"/trip/{trip_id}/chat", status_code=status.HTTP_302_FOUND)

@router.get("/api/trip/{trip_id}/messages")
async def get_messages(
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    since_id: int = 0
):
    """API endpoint for fetching new messages (for auto-refresh)."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    # Verify user is member
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    # Get messages since the given ID
    messages_statement = select(Message).where(
        Message.trip_id == trip_id,
        Message.id > since_id
    ).order_by(Message.timestamp.asc())
    messages_result = await session.execute(messages_statement)
    messages = messages_result.scalars().all()
    
    # Load user relationship
    for message in messages:
        await session.refresh(message, ["user"])
    
    # Convert to JSON
    messages_data = [
        {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp.strftime("%I:%M %p"),
            "user_name": msg.user.full_name or msg.user.email,
            "user_id": msg.user.id,
            "user_initial": (msg.user.full_name[0] if msg.user.full_name else msg.user.email[0]).upper()
        }
        for msg in messages
    ]
    
    return JSONResponse(messages_data)
