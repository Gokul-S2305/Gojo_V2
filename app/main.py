from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings

app = FastAPI(title="Gojo Trip Planner")

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

from app.routers import auth, dashboard, maps, gallery, chat, export as export_router
from app.database import init_db

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(maps.router)
app.include_router(gallery.router)
app.include_router(chat.router)
app.include_router(export_router.router)

@app.on_event("startup")
async def on_startup():
    await init_db()
    # Database initialized

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("base.html", {"request": request, "title": "Gojo - Home"})
