from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize Sentry if DSN is set
if getattr(settings, "sentry_dsn", None):
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1 if settings.is_production else 1.0,
        )
        logger.info("Sentry monitoring initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize Sentry: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    from app.database import init_db

    try:
        await init_db()
        logger.info("Startup complete — database ready.")
    except Exception as e:
        logger.critical(f"FATAL: Database initialization failed at startup: {e}")
        raise

    yield


app = FastAPI(title="Gojo Trip Planner", lifespan=lifespan)

# Setup SlowAPI Rate Limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add Session Middleware for OAuth2 and flash messages
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=settings.is_production,
    same_site="lax"
)

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = Path(__file__).parent / "templates"
templates_path.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=templates_path)

# Custom Date Filters
def format_date_filter(val):
    if not val:
        return ""
    if isinstance(val, str):
        try:
            from datetime import datetime
            val = datetime.strptime(val[:10], "%Y-%m-%d").date()
        except Exception:
            return val
    try:
        return val.strftime("%d %b %Y")
    except Exception:
        return str(val)

def format_date_range_filter(start, end):
    if not start or not end:
        return ""
    try:
        from datetime import datetime, date
        if isinstance(start, str):
            start = datetime.strptime(str(start)[:10], "%Y-%m-%d").date()
        if isinstance(end, str):
            end = datetime.strptime(str(end)[:10], "%Y-%m-%d").date()
        if start.year == end.year and start.month == end.month:
            return f"{start.day}–{end.day} {start.strftime('%b %Y')}"
        elif start.year == end.year:
            return f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
        else:
            return f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"
    except Exception:
        return f"{start} – {end}"

templates.env.filters["format_date"] = format_date_filter
templates.env.filters["format_date_range"] = format_date_range_filter

# Mount uploads directory for local fallback serving
uploads_path = Path(__file__).parent.parent / "uploads"
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

# Include Routers
from app.routers import auth, dashboard, maps, gallery, chat, export as export_router, documents, push

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(maps.router)
app.include_router(gallery.router)
app.include_router(chat.router)
app.include_router(export_router.router)
app.include_router(documents.router)
app.include_router(push.router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Resource not found"}, status_code=404)
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    logger.exception(f"Unhandled server error on {request.url.path}: {exc}")
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Internal server error"}, status_code=500)
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)


@app.get("/privacy")
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request, "user": None})


@app.get("/terms")
async def terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request, "user": None})


@app.get("/health")
async def health_check():
    """Health check endpoint for Render deployment."""
    return {"status": "ok", "service": "gojo-trip-planner"}


@app.get("/")
async def index(request: Request):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard", status_code=302)
