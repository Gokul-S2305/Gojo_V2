from fastapi import APIRouter, Request, Depends, Form, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import User
from app.auth_utils import get_password_hash, verify_password, create_access_token, oauth
from app.config import settings
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
        "secure": settings.is_production,   # Fix: use production flag
        "samesite": "lax",
        "max_age": 2592000 if remember else 1800,  # 30 days or 30 mins
    }


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

        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        user = result.scalar_one_or_none()

        if not user:
            user = User(email=email, full_name=full_name, password_hash=None, drive_connected=True)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif not user.drive_connected:
            user.drive_connected = True
            session.add(user)
            await session.commit()

        request.session['google_access_token'] = token.get('access_token')
        access_token = create_access_token(data={"sub": user.email, "user_id": user.id})

        resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        resp.set_cookie(**_make_cookie_params(access_token, remember=False))
        return resp

    except Exception as e:
        logger.error(f"OAuth error: {e}")
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": f"Authentication failed: {str(e)}"
        })


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
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    if result.scalar_one_or_none():
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": "Email already registered"
        })

    hashed_pw = get_password_hash(password)
    new_user = User(email=email, password_hash=hashed_pw, full_name=full_name)
    session.add(new_user)
    await session.commit()

    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    remember: bool = Form(False),
    session: AsyncSession = Depends(get_session)
):
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Invalid email or password"
        })

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})

    resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    resp.set_cookie(**_make_cookie_params(access_token, remember=remember))
    return resp


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response
