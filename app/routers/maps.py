from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink
from app.auth_utils import get_current_user
from app.config import settings
from pathlib import Path
import httpx
import google.generativeai as genai
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

CITY_COORDS = {
    "goa": (15.2993, 74.1240),
    "delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "jaipur": (26.9124, 75.7873),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "kerala": (10.8505, 76.2711),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
    "agra": (27.1767, 78.0081),
    "varanasi": (25.3176, 82.9739),
    "manali": (32.2396, 77.1887),
    "shimla": (31.1048, 77.1734),
    "ooty": (11.4102, 76.6950),
    "mysore": (12.2958, 76.6394),
    "pondicherry": (11.9416, 79.8083),
    "coorg": (12.3375, 75.8069),
}


async def get_coordinates_async(query: str):
    """Get coordinates using OpenStreetMap Nominatim API (async)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": query, "format": "json", "limit": 1}
            headers = {'User-Agent': 'GojoTripPlanner/2.0 (contact@gojotrips.com)'}
            response = await client.get(url, params=params, headers=headers)
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        logger.error(f"Geocoding error for {query}: {e}")

    query_lower = query.lower().strip()
    for city, coords in CITY_COORDS.items():
        if city in query_lower:
            return coords
    return None


async def get_osrm_route_async(start_coords, end_coords):
    """Get route geometry from OSRM (async)."""
    try:
        start_str = f"{start_coords[1]},{start_coords[0]}"
        end_str = f"{end_coords[1]},{end_coords[0]}"
        url = f"http://router.project-osrm.org/route/v1/driving/{start_str};{end_str}?overview=full&geometries=geojson"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            data = response.json()
            if data.get("code") == "Ok":
                route_coords = data["routes"][0]["geometry"]["coordinates"]
                return [(lat, lon) for lon, lat in route_coords]
    except Exception as e:
        logger.error(f"OSRM Routing error: {e}")
    return [start_coords, end_coords]


def get_gemini_recommendations(destination: str):
    """Get travel recommendations using Gemini API (sync, called in thread pool)."""
    if not settings.gemini_api_key:
        return {"hotels": [], "restaurants": [], "attractions": [], "travel_tips": []}

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
Act as an expert travel guide. For the destination "{destination}", provide accurate, real top recommendations.

Return ONLY a raw JSON object with this exact structure (no markdown, no backticks, no comments):
{{
    "hotels": [
        {{"name": "Hotel Name", "rating": 4.5, "price": "Luxury", "area": "Location area", "sentiment": "One sentence description"}}
    ],
    "restaurants": [
        {{"name": "Restaurant Name", "rating": 4.8, "cuisine": "Local/Indian/etc", "area": "Location area", "sentiment": "One sentence description"}}
    ],
    "attractions": [
        {{"name": "Place Name", "type": "History/Nature/Beach/Temple/etc", "area": "Location", "sentiment": "One sentence description"}}
    ],
    "travel_tips": [
        {{"tip": "Transport/Safety/Food/Weather/etc", "description": "Practical advice for travelers"}}
    ]
}}
Provide 5 items per category. Use real, well-known places. Be accurate and specific.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```json"):
            text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
        elif text.startswith("```"):
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return {"hotels": [], "restaurants": [], "attractions": [], "travel_tips": []}


def get_gemini_itinerary(destination: str, duration: int, start_location: str = None):
    """Get AI-generated itinerary suggestions using Gemini API."""
    if not settings.gemini_api_key:
        return []

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        start_info = f" starting from {start_location}" if start_location else ""
        prompt = f"""
Act as an expert travel planner. Create a detailed, accurate {duration}-day itinerary for a trip to "{destination}"{start_info}.

Return ONLY a raw JSON array (no markdown, no backticks):
[
  {{
    "day": 1,
    "items": [
      {{
        "time": "09:00",
        "activity": "Activity Name",
        "location": "Specific Place Name",
        "category": "Sightseeing",
        "description": "Brief description of what to do and why it's special",
        "tips": "Practical tip for this activity"
      }}
    ]
  }}
]

Categories: Sightseeing, Food, Hotel, Transport, Activity, Shopping, Nature, Culture
Include 4-5 items per day. Use real, specific place names. Make it practical and accurate.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```json"):
            text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
        elif text.startswith("```"):
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"Gemini itinerary error: {e}")
        return []


@router.get("/maps", response_class=HTMLResponse)
async def maps_root(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    statement = select(Trip).join(TripUserLink).where(
        TripUserLink.user_id == user.id
    ).order_by(Trip.id.desc()).limit(1)
    result = await session.execute(statement)
    trip = result.scalar_one_or_none()

    if trip:
        return await trip_map(request, trip.id, user, session)

    return templates.TemplateResponse("map.html", {
        "request": request, "user": user, "trip": None,
        "start_coords": None, "destination_coords": [20.5937, 78.9629],
        "route_path": [], "recommendations": {"hotels": [], "restaurants": [], "attractions": [], "travel_tips": []}
    })


@router.get("/trip/{trip_id}/map", response_class=HTMLResponse)
async def trip_map(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()

    if not trip:
        return RedirectResponse("/dashboard", status_code=302)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=302)

    destination_coords = await get_coordinates_async(trip.destination)
    start_coords = await get_coordinates_async(trip.start_location) if trip.start_location else None

    if not destination_coords:
        destination_coords = (20.5937, 78.9629)

    route_path = []
    if start_coords:
        route_path = await get_osrm_route_async(start_coords, destination_coords)

    import asyncio
    recommendations = await asyncio.get_event_loop().run_in_executor(
        None, get_gemini_recommendations, trip.destination
    )

    return templates.TemplateResponse("map.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "start_coords": list(start_coords) if start_coords else None,
        "destination_coords": list(destination_coords),
        "route_path": [[lat, lon] for lat, lon in route_path],
        "recommendations": recommendations,
        "maps_api_key": settings.google_maps_api_key,
    })


@router.get("/api/trip/{trip_id}/recommendations")
async def get_recommendations(
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """API: Get AI recommendations for a trip."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()

    if not trip:
        return JSONResponse({"error": "Trip not found"}, status_code=404)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    import asyncio
    recommendations = await asyncio.get_event_loop().run_in_executor(
        None, get_gemini_recommendations, trip.destination
    )
    return JSONResponse(recommendations)


@router.get("/api/trip/{trip_id}/ai-itinerary")
async def get_ai_itinerary(
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """API: Get AI-generated itinerary suggestions for a trip."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()

    if not trip:
        return JSONResponse({"error": "Trip not found"}, status_code=404)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    duration = (trip.end_date - trip.start_date).days + 1

    import asyncio
    itinerary = await asyncio.get_event_loop().run_in_executor(
        None, get_gemini_itinerary, trip.destination, duration, trip.start_location
    )
    return JSONResponse(itinerary)
