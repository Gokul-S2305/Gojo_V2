from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy import text
from app.database import get_session
from app.models import User, Trip, TripUserLink, Message
from app.auth_utils import get_current_user
from pathlib import Path
from typing import Dict, List
import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


class ConnectionManager:
    """Manages WebSocket connections per trip."""

    def __init__(self):
        # trip_id -> list of (websocket, user_id, user_name)
        self.active_connections: Dict[int, List[tuple]] = {}

    async def connect(self, websocket: WebSocket, trip_id: int, user_id: int, user_name: str):
        await websocket.accept()
        if trip_id not in self.active_connections:
            self.active_connections[trip_id] = []
        self.active_connections[trip_id].append((websocket, user_id, user_name))

    def disconnect(self, websocket: WebSocket, trip_id: int):
        if trip_id in self.active_connections:
            self.active_connections[trip_id] = [
                conn for conn in self.active_connections[trip_id] if conn[0] != websocket
            ]

    async def broadcast_to_trip(self, trip_id: int, data: dict):
        if trip_id not in self.active_connections:
            return
        dead = []
        for conn_tuple in self.active_connections[trip_id]:
            websocket = conn_tuple[0]
            try:
                await websocket.send_json(data)
            except Exception:
                dead.append(conn_tuple)
        for d in dead:
            self.active_connections[trip_id].remove(d)

    def get_online_users(self, trip_id: int) -> List[dict]:
        if trip_id not in self.active_connections:
            return []
        seen = set()
        users = []
        for _, user_id, user_name in self.active_connections[trip_id]:
            if user_id not in seen:
                seen.add(user_id)
                users.append({"id": user_id, "name": user_name})
        return users


manager = ConnectionManager()


@router.websocket("/ws/trip/{trip_id}/chat")
async def websocket_chat(
    websocket: WebSocket,
    trip_id: int,
    session: AsyncSession = Depends(get_session)
):
    """WebSocket endpoint for real-time trip chat."""
    # Authenticate via cookie
    access_token = websocket.cookies.get("access_token")
    user = None

    if access_token:
        try:
            from app.auth_utils import get_current_user as _get_user
            # Manual token decode since we can't use Depends directly in WS
            from jose import jwt
            from app.config import settings as cfg
            scheme, token = access_token.split()
            payload = jwt.decode(token, cfg.secret_key, algorithms=[cfg.algorithm])
            user_id = payload.get("user_id")
            if user_id:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"WS auth error: {e}")

    if not user:
        await websocket.close(code=4001)
        return

    # Verify trip membership
    link_result = await session.execute(
        select(TripUserLink).where(
            TripUserLink.trip_id == trip_id,
            TripUserLink.user_id == user.id
        )
    )
    if not link_result.scalar_one_or_none():
        await websocket.close(code=4003)
        return

    user_name = user.full_name or user.email
    user_initial = user_name[0].upper()

    await manager.connect(websocket, trip_id, user.id, user_name)

    # Notify others that user joined
    await manager.broadcast_to_trip(trip_id, {
        "type": "user_joined",
        "user_id": user.id,
        "user_name": user_name,
        "online_users": manager.get_online_users(trip_id)
    })

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "").strip()

            if not content or len(content) > 2000:
                continue

            # Save message to DB
            new_message = Message(trip_id=trip_id, user_id=user.id, content=content)
            session.add(new_message)
            await session.commit()
            await session.refresh(new_message)

            # Broadcast to all trip members
            await manager.broadcast_to_trip(trip_id, {
                "type": "message",
                "id": new_message.id,
                "content": content,
                "timestamp": new_message.timestamp.strftime("%I:%M %p"),
                "user_id": user.id,
                "user_name": user_name,
                "user_initial": user_initial,
            })

            # Send push notification to offline members
            try:
                from app.routers.push import send_trip_notification
                await send_trip_notification(
                    trip_id=trip_id,
                    sender_id=user.id,
                    sender_name=user_name,
                    message=content,
                    session=session
                )
            except Exception as e:
                logger.debug(f"Push notification error: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket, trip_id)
        await manager.broadcast_to_trip(trip_id, {
            "type": "user_left",
            "user_id": user.id,
            "user_name": user_name,
            "online_users": manager.get_online_users(trip_id)
        })


@router.get("/trip/{trip_id}/chat", response_class=HTMLResponse)
async def trip_chat(
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

    # Get messages with user info via JOIN (fixes N+1)
    from app.models import User as UserModel
    messages_statement = select(Message, UserModel).join(
        UserModel, Message.user_id == UserModel.id
    ).where(Message.trip_id == trip_id).order_by(Message.timestamp.asc())
    messages_result = await session.execute(messages_statement)
    messages_data = messages_result.all()

    messages = [
        {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp.strftime("%I:%M %p"),
            "user_id": msg.user_id,
            "user_name": msg_user.full_name or msg_user.email,
            "user_initial": (msg_user.full_name or msg_user.email)[0].upper(),
        }
        for msg, msg_user in messages_data
    ]

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "messages": messages,
    })


@router.get("/api/trip/{trip_id}/messages")
async def get_messages(
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    since_id: int = 0
):
    """Fallback polling API for messages."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    from app.models import User as UserModel
    messages_statement = select(Message, UserModel).join(
        UserModel, Message.user_id == UserModel.id
    ).where(
        Message.trip_id == trip_id,
        Message.id > since_id
    ).order_by(Message.timestamp.asc())

    messages_result = await session.execute(messages_statement)
    messages_data = messages_result.all()

    messages = [
        {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp.strftime("%I:%M %p"),
            "user_id": msg.user_id,
            "user_name": msg_user.full_name or msg_user.email,
            "user_initial": (msg_user.full_name or msg_user.email)[0].upper(),
        }
        for msg, msg_user in messages_data
    ]

    return JSONResponse(messages)
