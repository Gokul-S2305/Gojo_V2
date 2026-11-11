from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, TripRecommendation, ItineraryItem
from app.auth_utils import get_current_user
from app.config import settings
from app.limiter import limiter
from pathlib import Path
from datetime import datetime
import httpx
import google.generativeai as genai
import json
import logging
import asyncio

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
    if not query:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": query, "format": "json", "limit": 1}
            headers = {'User-Agent': 'GojoTripPlanner/2.0 (contact@gojotrips.com)'}
            response = await client.get(url, params=params, headers=headers)
            data = response.json()
            if data and len(data) > 0:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        logger.warning(f"Geocoding lookup error for {query}: {e}")

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
        url = f"https://router.project-osrm.org/route/v1/driving/{start_str};{end_str}?overview=full&geometries=geojson"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            data = response.json()
            if data.get("code") == "Ok":
                route_coords = data["routes"][0]["geometry"]["coordinates"]
                return [(lat, lon) for lon, lat in route_coords]
    except Exception as e:
        logger.warning(f"OSRM Routing error: {e}")
    return [start_coords, end_coords]


BUDGET_MAP = {
    "budget": "Budget-friendly (₹ / under ₹2,000 per night)",
    "mid": "Mid-range (₹₹ / ₹2,000 - ₹6,000 per night)",
    "luxury": "Luxury / Premium (₹₹₹ / ₹6,000+ per night)"
}


def get_gemini_recommendations(destination: str, budget_tier: str = "mid") -> dict:
    """Generate recommendations without invented ratings and with strict JSON mode."""
    if not settings.gemini_api_key:
        return _fallback_recommendations(destination, budget_tier)

    try:
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config={"response_mime_type": "application/json"}
        )
        budget_desc = BUDGET_MAP.get(budget_tier, BUDGET_MAP["mid"])
        prompt = f"""
Act as a travel guide for "{destination}". Budget preference is {budget_desc}.
Provide real, authentic recommendations for this destination.
IMPORTANT: Do NOT invent ratings (like 4.8 or 5.0). Provide accurate names, locations/neighborhoods, estimated price tier, and a concise 1-sentence tip.

Return a JSON object with this schema:
{{
  "hotels": [
    {{"name": "Hotel Name", "area": "Neighborhood/Area", "price_range": "₹ / ₹₹ / ₹₹₹", "description": "Authentic description and vibe"}}
  ],
  "restaurants": [
    {{"name": "Restaurant Name", "area": "Neighborhood/Area", "cuisine": "Cuisine type", "price_range": "₹ / ₹₹ / ₹₹₹", "description": "Signature dish or vibe"}}
  ],
  "attractions": [
    {{"name": "Attraction Name", "area": "Location", "category": "Beach/Heritage/Nature/Market", "description": "Best time or highlight"}}
  ],
  "travel_tips": [
    {{"title": "Local Transport/Best season/Custom", "advice": "Practical advice for travelers"}}
  ]
}}
Provide 4-5 items per section.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        data = json.loads(text)
        data["is_fallback"] = False
        return data
    except Exception as e:
        logger.warning(f"Gemini API error for {destination}: {e}")
        fallback = _fallback_recommendations(destination, budget_tier)
        fallback["error"] = "AI recommendations temporarily unavailable. Showing local guide picks."
        fallback["is_fallback"] = True
        return fallback


def _fallback_recommendations(destination: str, budget_tier: str) -> dict:
    return {
        "hotels": [
            {"name": f"Central Heritage Stay ({destination})", "area": "City Center", "price_range": "₹₹", "description": "Comfortable, well-located stay close to major sights."},
            {"name": f"Palm View Retreat", "area": "Quiet Outskirts", "price_range": "₹₹", "description": "Relaxing atmosphere with garden views and modern amenities."}
        ],
        "restaurants": [
            {"name": f"Old Town Kitchen", "area": "Market District", "cuisine": "Local authentic", "price_range": "₹₹", "description": "Famous for regional curries and fresh specialties."},
            {"name": f"Street Flavors Hub", "area": "Main Bazaar", "cuisine": "Street Food", "price_range": "₹", "description": "Quick bites, fresh snacks, and local favorites."}
        ],
        "attractions": [
            {"name": f"Historic Old Town & Market", "area": "Central", "category": "Heritage", "description": "Wander through centuries-old streets, crafts shops, and vibrant architecture."},
            {"name": f"Sunset Viewpoint", "area": "Hilltop / Coast", "category": "Nature", "description": "Best visited around 5:30 PM for panoramic evening vistas."}
        ],
        "travel_tips": [
            {"title": "Local Transport", "advice": "Use app-based cabs or pre-negotiate autorickshaw fares before starting your ride."},
            {"title": "Timing", "advice": "Visit popular outdoor sights early morning to beat both the heat and rush-hour crowds."}
        ]
    }


def get_gemini_itinerary(destination: str, duration: int, start_location: str = None) -> list:
    """Generate structured AI itinerary without invented numbers."""
    if not settings.gemini_api_key:
        return _fallback_itinerary(destination, duration)

    try:
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config={"response_mime_type": "application/json"}
        )
        start_info = f" starting from {start_location}" if start_location else ""
        prompt = f"""
Create a practical, real {duration}-day itinerary for a trip to "{destination}"{start_info}.
Do NOT invent ratings or bogus claims. Focus on realistic day flow and geographical proximity.

Return a JSON array of days:
[
  {{
    "day": 1,
    "theme": "Arrival & City Highlights",
    "items": [
      {{
        "time": "09:30",
        "activity": "Activity Name",
        "location": "Specific place name",
        "category": "Sightseeing",
        "description": "What to see or do here"
      }}
    ]
  }}
]
Include 3-4 items per day.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Gemini itinerary error: {e}")
        return _fallback_itinerary(destination, duration)


def _fallback_itinerary(destination: str, duration: int) -> list:
    itinerary = []
    for day in range(1, duration + 1):
        itinerary.append({
            "day": day,
            "theme": f"Explore {destination} - Day {day}",
            "items": [
                {"time": "09:00", "activity": f"Morning walk & local breakfast", "location": "Old Town", "category": "Food", "description": "Sample fresh local breakfast and coffee."},
                {"time": "11:30", "activity": f"Visit {destination} landmarks", "location": "City Center", "category": "Sightseeing", "description": "Explore architecture and cultural exhibitions."},
                {"time": "15:00", "activity": f"Afternoon market & craft shopping", "location": "Bazaar", "category": "Activity", "description": "Pick up regional crafts, spices, and souvenirs."},
                {"time": "18:00", "activity": f"Sunset & Dinner", "location": "Promenade / Viewpoint", "category": "Food", "description": "Relax and enjoy dinner with local specialties."}
            ]
        })
    return itinerary


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/maps", response_class=HTMLResponse)
async def maps_root(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    statement = (
        select(Trip)
        .join(TripUserLink)
        .where(TripUserLink.user_id == user.id)
        .order_by(Trip.id.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    trip = result.scalar_one_or_none()

    if trip:
        return await trip_map(request, trip.id, user, session)

    return templates.TemplateResponse("map.html", {
        "request": request, "user": user, "trip": None,
        "start_coords": None, "destination_coords": [20.5937, 78.9629],
        "route_path": [], "recommendations": _fallback_recommendations("India", "mid"),
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
        raise HTTPException(status_code=404, detail="Trip not found")

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Trip not found")

    destination_coords = await get_coordinates_async(trip.destination)
    start_coords = await get_coordinates_async(trip.start_location) if trip.start_location else None

    if not destination_coords:
        destination_coords = (20.5937, 78.9629)

    route_path = []
    if start_coords:
        route_path = await get_osrm_route_async(start_coords, destination_coords)

    # Check cached recommendations
    rec_stmt = select(TripRecommendation).where(
        TripRecommendation.trip_id == trip_id,
        TripRecommendation.budget_tier == "mid",
        TripRecommendation.category == "all"
    )
    rec_result = await session.execute(rec_stmt)
    cached = rec_result.scalar_one_or_none()

    if cached:
        try:
            recommendations = json.loads(cached.data_json)
        except Exception:
            recommendations = None
    else:
        loop = asyncio.get_event_loop()
        recommendations = await loop.run_in_executor(
            None, get_gemini_recommendations, trip.destination, "mid"
        )
        # Cache to DB
        new_rec = TripRecommendation(
            trip_id=trip_id,
            budget_tier="mid",
            category="all",
            data_json=json.dumps(recommendations)
        )
        session.add(new_rec)
        await session.commit()

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
@limiter.limit("10/minute")
async def get_recommendations_api(
    request: Request,
    trip_id: int,
    budget: str = Query("mid", enum=["budget", "mid", "luxury"]),
    refresh: bool = Query(False),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
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

    # Check cache if not refresh
    if not refresh:
        rec_stmt = select(TripRecommendation).where(
            TripRecommendation.trip_id == trip_id,
            TripRecommendation.budget_tier == budget,
            TripRecommendation.category == "all"
        )
        rec_res = await session.execute(rec_stmt)
        cached = rec_res.scalar_one_or_none()
        if cached:
            try:
                return JSONResponse(json.loads(cached.data_json))
            except Exception:
                pass

    loop = asyncio.get_event_loop()
    recommendations = await loop.run_in_executor(
        None, get_gemini_recommendations, trip.destination, budget
    )

    # Update or save cache
    rec_stmt = select(TripRecommendation).where(
        TripRecommendation.trip_id == trip_id,
        TripRecommendation.budget_tier == budget,
        TripRecommendation.category == "all"
    )
    rec_res = await session.execute(rec_stmt)
    existing = rec_res.scalar_one_or_none()

    if existing:
        existing.data_json = json.dumps(recommendations)
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        new_rec = TripRecommendation(
            trip_id=trip_id,
            budget_tier=budget,
            category="all",
            data_json=json.dumps(recommendations)
        )
        session.add(new_rec)

    await session.commit()
    return JSONResponse(recommendations)


@router.get("/api/trip/{trip_id}/ai-itinerary")
@limiter.limit("10/minute")
async def get_ai_itinerary_api(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
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
    loop = asyncio.get_event_loop()
    itinerary = await loop.run_in_executor(
        None, get_gemini_itinerary, trip.destination, duration, trip.start_location
    )
    return JSONResponse(itinerary)


@router.post("/api/trip/{trip_id}/itinerary/from-ai")
async def add_ai_item_to_itinerary(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Adds a recommendation or AI plan suggestion directly into the trip itinerary."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()

    if not link:
        return JSONResponse({"error": "Trip not found"}, status_code=404)
    if link.role != "organizer":
        return JSONResponse({"error": "Organizer permissions required"}, status_code=403)

    body = await request.json()
    day_number = int(body.get("day_number", 1))
    activity = body.get("activity") or body.get("name")
    location = body.get("location") or body.get("area")
    description = body.get("description")
    category = body.get("category", "Activity")
    time_val = body.get("time", "10:00")

    if not activity:
        return JSONResponse({"error": "Activity name is required"}, status_code=400)

    new_item = ItineraryItem(
        trip_id=trip_id,
        day_number=day_number,
        time=time_val,
        activity=activity,
        location=location,
        description=description,
        category=category
    )
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)

    return JSONResponse({"status": "ok", "item_id": new_item.id})
