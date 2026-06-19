from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings


import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    from app.database import init_db
    asyncio.create_task(init_db())
    yield
    # Shutdown cleanup (if needed in future)


app = FastAPI(title="Gojo Trip Planner", lifespan=lifespan)

# Add Session Middleware for OAuth2
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = Path(__file__).parent / "templates"
templates_path.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=templates_path)

# Mount uploads directory
uploads_path = Path(__file__).parent.parent / "uploads"
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

from app.routers import auth, dashboard, maps, gallery, chat, export as export_router, documents, push

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(maps.router)
app.include_router(gallery.router)
app.include_router(chat.router)
app.include_router(export_router.router)
app.include_router(documents.router)
app.include_router(push.router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("base.html", {"request": request, "title": "Gojo - Home"})
