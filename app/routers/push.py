"""
Web Push Notification support for Gojo Trip Planner.
Uses the pywebpush library for VAPID-based Web Push.
"""
from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, PushSubscription, TripUserLink
from app.auth_utils import get_current_user
from app.config import settings
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# VAPID keys are loaded from settings (generated once and stored in .env)
VAPID_PRIVATE_KEY = getattr(settings, 'vapid_private_key', '')
VAPID_PUBLIC_KEY = getattr(settings, 'vapid_public_key', '')
VAPID_CLAIMS = {"sub": f"mailto:{getattr(settings, 'email_from', 'noreply@gojotrips.com')}"}


@router.get("/api/push/vapid-key")
async def get_vapid_key():
    """Return the VAPID public key for client-side push subscription."""
    return JSONResponse({"publicKey": VAPID_PUBLIC_KEY})


@router.post("/api/push/subscribe")
async def subscribe_push(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Register a Web Push subscription for the current user."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
        endpoint = body.get("endpoint", "")
        keys = body.get("keys", {})
        p256dh = keys.get("p256dh", "")
        auth = keys.get("auth", "")

        if not all([endpoint, p256dh, auth]):
            return JSONResponse({"error": "Invalid subscription data"}, status_code=400)

        # Check for existing subscription by endpoint
        existing_stmt = select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == endpoint
        )
        existing_result = await session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if not existing:
            sub = PushSubscription(
                user_id=user.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth
            )
            session.add(sub)
            await session.commit()

        return JSONResponse({"status": "subscribed"})

    except Exception as e:
        logger.error(f"Push subscribe error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/push/unsubscribe")
async def unsubscribe_push(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Remove push subscriptions for the current user."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
        endpoint = body.get("endpoint")

        stmt = select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == endpoint
        )
        result = await session.execute(stmt)
        sub = result.scalar_one_or_none()
        if sub:
            await session.delete(sub)
            await session.commit()

        return JSONResponse({"status": "unsubscribed"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def send_trip_notification(
    trip_id: int,
    sender_id: int,
    sender_name: str,
    message: str,
    session: AsyncSession
):
    """Send push notifications to all trip members except the sender."""
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return  # Skip if VAPID keys not configured

    try:
        from pywebpush import webpush, WebPushException

        # Get all trip members except sender
        members_stmt = select(TripUserLink).where(
            TripUserLink.trip_id == trip_id,
            TripUserLink.user_id != sender_id
        )
        members_result = await session.execute(members_stmt)
        member_links = members_result.scalars().all()

        member_ids = [link.user_id for link in member_links]
        if not member_ids:
            return

        # Get push subscriptions for those members
        subs_stmt = select(PushSubscription).where(
            PushSubscription.user_id.in_(member_ids)
        )
        subs_result = await session.execute(subs_stmt)
        subscriptions = subs_result.scalars().all()

        payload = json.dumps({
            "title": f"Gojo — {sender_name}",
            "body": message[:100] + ("..." if len(message) > 100 else ""),
            "icon": "/static/images/icon-192.png",
            "badge": "/static/images/icon-192.png",
            "data": {"trip_id": trip_id, "url": f"/trip/{trip_id}/chat"},
        })

        dead_subs = []
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS,
                )
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    dead_subs.append(sub)
                else:
                    logger.warning(f"Push send failed: {e}")
            except Exception as e:
                logger.warning(f"Push error: {e}")

        # Cleanup expired subscriptions
        for dead in dead_subs:
            await session.delete(dead)
        if dead_subs:
            await session.commit()

    except ImportError:
        logger.debug("pywebpush not installed, skipping push notifications")
    except Exception as e:
        logger.error(f"send_trip_notification error: {e}")
