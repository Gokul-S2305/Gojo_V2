"""
Authentication utilities: password hashing, JWT creation/verification, OAuth.
Uses PyJWT instead of python-jose (jose has known CVEs and is unmaintained).
"""
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
from fastapi import Request, Depends, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import User
from sqlmodel import select

from app.config import settings
from authlib.integrations.starlette_client import OAuth

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url=settings.google_discovery_url,
    client_kwargs={
        'scope': 'openid email profile',
        'timeout': 10.0
    }
)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    try:
        return bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise ValueError("Failed to hash password")


def validate_password_strength(password: str) -> Optional[str]:
    """
    Returns an error message string if the password is too weak, else None.
    Rules: min 8 chars, at least one uppercase, at least one digit.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one digit."
    return None

# ---------------------------------------------------------------------------
# JWT tokens (PyJWT)
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    try:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
        )
        to_encode["exp"] = expire
        token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        logger.info(f"Access token created for user: {data.get('user_id')}")
        return token
    except Exception as e:
        logger.error(f"Token creation error: {e}")
        raise ValueError("Failed to create access token")


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None

# ---------------------------------------------------------------------------
# Current user dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    access_token: Optional[str] = Cookie(None),
    session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """Get the authenticated user from the access_token cookie."""
    if not access_token:
        return None

    try:
        # Cookie value format: "Bearer <token>"
        parts = access_token.split()
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else access_token
        payload = decode_access_token(token)
        if payload is None:
            return None
        user_id = payload.get("user_id")
        if user_id is None:
            logger.warning("Token payload missing user_id")
            return None
    except Exception as e:
        logger.error(f"Unexpected error parsing token: {e}")
        return None

    try:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            logger.debug(f"Authenticated user: {user.email}")
        else:
            logger.warning(f"No user found for id: {user_id}")
        return user
    except Exception as e:
        logger.error(f"DB error in get_current_user: {e}")
        return None
