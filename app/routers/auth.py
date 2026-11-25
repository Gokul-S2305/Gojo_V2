from fastapi import APIRouter, Request, Depends, Form, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import User
from app.auth_utils import (
    get_password_hash, verify_password, create_access_token,
    validate_password_strength, get_current_user, oauth
)
from app.config import settings
from app.limiter import limiter
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _make_cookie_params(access_token: str, remember: bool = False) -> dict:
    """Build consistent, secure cookie parameters."""
    return {
        "key": "access_token",
        "value": f"Bearer {access_token}",
        "httponly": True,
        "secure": settings.is_production,
        "samesite": "lax",
        "max_age": 2592000 if remember else settings.access_token_expire_minutes * 60,
    }


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@router.get("/login/google")
async def login_google(request: Request):
    """Initiate Google OAuth login."""
    redirect_uri = request.url_for('auth_google')
    return await oauth.google.authorize_redirect(request, str(redirect_uri))


@router.get("/auth/google")
async def auth_google(request: Request, session: AsyncSession = Depends(get_session)):
    """Callback for Google OAuth."""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            return templates.TemplateResponse("auth/login.html", {
                "request": request, "error": "Failed to fetch user info from Google"
            })

        if not user_info.get('email_verified'):
            return templates.TemplateResponse("auth/login.html", {
                "request": request, "error": "Google email not verified. Login rejected."
            })

        email = user_info.get('email')
        full_name = user_info.get('name')

        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            user = User(email=email, full_name=full_name, password_hash=None, drive_connected=False)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        request.session['google_access_token'] = token.get('access_token')
        access_token = create_access_token(data={"sub": user.email, "user_id": user.id})

        next_url = request.session.pop("next", "/dashboard")
        resp = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
        resp.set_cookie(**_make_cookie_params(access_token, remember=False))
        return resp

    except Exception as e:
        logger.error(f"OAuth error: {e}")
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Authentication failed. Please try again."
        })


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    session: AsyncSession = Depends(get_session)
):
    # Validate password strength
    pw_error = validate_password_strength(password)
    if pw_error:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": pw_error,
            "email": email, "full_name": full_name
        })

    # Check duplicate email
    result = await session.execute(select(User).where(User.email == email.lower().strip()))
    if result.scalar_one_or_none():
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": "An account with that email already exists.",
            "email": email, "full_name": full_name
        })

    hashed_pw = get_password_hash(password)
    new_user = User(
        email=email.lower().strip(),
        password_hash=hashed_pw,
        full_name=full_name.strip()
    )
    session.add(new_user)
    await session.commit()

    return RedirectResponse(url="/login?registered=1", status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    registered = request.query_params.get("registered")
    next_url = request.query_params.get("next")
    if next_url and next_url.startswith("/"):
        request.session["next"] = next_url
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "success": "Account created! You can now log in." if registered else None
    })


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    remember: bool = Form(False),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(User).where(User.email == email.lower().strip())
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Invalid email or password"
        })

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})

    next_url = request.session.pop("next", "/dashboard")
    resp = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(**_make_cookie_params(access_token, remember=remember))
    return resp


# ---------------------------------------------------------------------------
# Password Update
# ---------------------------------------------------------------------------

@router.post("/profile/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    user_db = await session.get(User, user.id)
    if not user_db or not user_db.password_hash or not verify_password(current_password, user_db.password_hash):
        return RedirectResponse("/dashboard?error=Current+password+is+incorrect", status_code=status.HTTP_302_FOUND)

    pw_error = validate_password_strength(new_password)
    if pw_error:
        return RedirectResponse(f"/dashboard?error={pw_error}", status_code=status.HTTP_302_FOUND)

    user_db.password_hash = get_password_hash(new_password)
    session.add(user_db)
    await session.commit()

    return RedirectResponse("/dashboard?msg=Password+updated+successfully", status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response
