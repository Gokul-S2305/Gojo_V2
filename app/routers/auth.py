from fastapi import APIRouter, Request, Depends, Form, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import User
from app.auth_utils import get_password_hash, verify_password, create_access_token
from pathlib import Path

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

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
    # Check existing user
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    if result.scalar_one_or_none():
        return templates.TemplateResponse("auth/register.html", {"request": request, "error": "Email already registered"})
    
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
    session: AsyncSession = Depends(get_session)
):
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "Invalid credentials"})
    
    # Create JWT
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    
    # Redirect to dashboard with secure cookie
    resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,  # Prevent JavaScript access
        secure=True,    # Only send over HTTPS (disable in dev if needed)
        samesite="lax", # CSRF protection
        max_age=1800    # 30 minutes
    )
    return resp

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response
