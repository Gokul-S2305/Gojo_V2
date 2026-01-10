import bcrypt
from datetime import datetime, timedelta
from jose import jwt, JWTError
from typing import Optional
import logging

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    try:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise ValueError("Failed to hash password")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        logger.info(f"Access token created for user: {data.get('user_id')}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Token creation error: {e}")
        raise ValueError("Failed to create access token")

from fastapi import Request, Depends, HTTPException, status, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import User
from sqlmodel import select

async def get_current_user(
    request: Request, 
    access_token: Optional[str] = Cookie(None), 
    session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """Get the current authenticated user from the access token cookie."""
    if not access_token:
        return None
    
    try:
        # Parse Bearer token
        scheme, token = access_token.split()
        if scheme.lower() != 'bearer':
            logger.warning("Invalid token scheme")
            return None
        
        # Decode JWT
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("user_id")
        
        if user_id is None:
            logger.warning("Token missing user_id")
            return None
            
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None
    except ValueError as e:
        logger.warning(f"Token parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}")
        return None

    # Fetch user from database
    try:
        statement = select(User).where(User.id == user_id)
        result = await session.execute(statement)
        user = result.scalar_one_or_none()
        
        if user:
            logger.debug(f"User authenticated: {user.email}")
        else:
            logger.warning(f"User not found for id: {user_id}")
            
        return user
    except Exception as e:
        logger.error(f"Database error in get_current_user: {e}")
        return None
