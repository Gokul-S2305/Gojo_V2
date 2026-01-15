from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink
from app.auth_utils import get_current_user
from app.config import settings
from pathlib import Path
import folium
from folium import plugins
import requests
import google.generativeai as genai
import json
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# City coordinates for map centering (Fallback)
CITY_COORDS = {
    "goa": (15.2993, 74.1240),
    "delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "jaipur": (26.9124, 75.7873),
    "bangalore": (12.9716, 77.5946),
    "kerala": (10.8505, 76.2711),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
}

def get_coordinates(query: str):
    """Get coordinates using OpenStreetMap Nominatim API."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1
        }
        headers = {'User-Agent': 'GojoTripPlanner/1.0'}
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        logger.error(f"Geocoding error for {query}: {e}")
        
    # Fallback to predefined list
    query_lower = query.lower().strip()
    for city, coords in CITY_COORDS.items():
        if city in query_lower:
            return coords
            
    return None

def get_osrm_route(start_coords, end_coords):
    """Get route geometry from OSRM."""
    try:
        # OSRM expects: lon,lat
        start_str = f"{start_coords[1]},{start_coords[0]}"
        end_str = f"{end_coords[1]},{end_coords[0]}"
        url = f"http://router.project-osrm.org/route/v1/driving/{start_str};{end_str}?overview=full&geometries=geojson"
        
        response = requests.get(url)
        data = response.json()
        
        if data["code"] == "Ok":
            # Extract coordinates (lon, lat) -> convert to (lat, lon) for folium
            route_coords = data["routes"][0]["geometry"]["coordinates"]
            return [(lat, lon) for lon, lat in route_coords]
    except Exception as e:
        logger.error(f"OSRM Routing error: {e}")
    
    return [start_coords, end_coords] # Fallback to straight line

def get_gemini_recommendations(destination: str):
    """Get travel recommendations using Gemini API."""
    if not settings.gemini_api_key:
        return {"hotels": [], "restaurants": [], "attractions": []}

    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Act as a travel guide. For the destination "{destination}", provide top recommendations.
        Return ONLY a raw JSON object with this exact structure (no markdown, no backticks):
        {{
            "hotels": [
                {{"name": "Hotel Name", "rating": 4.5, "price": "High/Mid/Budget", "sentiment": "Brief description"}}
            ],
            "restaurants": [
                {{"name": "Restaurant Name", "rating": 4.8, "cuisine": "Type", "sentiment": "Brief description"}}
            ],
            "attractions": [
                {{"name": "Attraction Name", "type": "History/Nature/etc", "sentiment": "Brief description"}}
            ]
        }}
        Provide 5 items for each category.
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up any potential markdown formatting
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
            
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return {"hotels": [], "restaurants": [], "attractions": []}

@router.get("/trip/{trip_id}/map", response_class=HTMLResponse)
async def trip_map(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    
    # Get trip
    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()
    
    if not trip:
        return RedirectResponse("/dashboard", status_code=302)
    
    # Check permissions
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=302)
    
    # 1. Geocode Start and Destination
    destination_coords = get_coordinates(trip.destination)
    start_coords = get_coordinates(trip.start_location) if trip.start_location else None
    
    # Fallback if geocoding fails completely
    if not destination_coords:
         destination_coords = (20.5937, 78.9629) # India Center
    
    # 2. Initialize Map
    map_center = destination_coords
    if start_coords:
        map_center = ((start_coords[0] + destination_coords[0])/2, (start_coords[1] + destination_coords[1])/2)
        
    m = folium.Map(location=map_center, zoom_start=6 if start_coords else 12)
    
    # 3. Add Destination Marker
    folium.Marker(
        destination_coords,
        popup=f"<b>{trip.destination}</b><br>Destination",
        icon=folium.Icon(color="red", icon="flag", prefix="fa")
    ).add_to(m)
    
    # 4. Handle Route (if start location exists)
    if start_coords:
        folium.Marker(
            start_coords,
            popup=f"<b>{trip.start_location}</b><br>Start",
            icon=folium.Icon(color="green", icon="play", prefix="fa")
        ).add_to(m)
        
        # Get OSRM Route
        route_path = get_osrm_route(start_coords, destination_coords)
        folium.PolyLine(
            route_path,
            weight=5,
            color="blue",
            opacity=0.8,
            tooltip=f"Route: {trip.start_location} ➝ {trip.destination}"
        ).add_to(m)

    # 5. Get AI Recommendations
    recommendations = get_gemini_recommendations(trip.destination)
    
    # 6. Plot Recommendations (Attempt to geocode them dynamically or fuzzy plot)
    # Since geocoding every recommendation is slow and might get rate-limited by Nominatim,
    # we will just pass them to the template to show in the sidebar, 
    # OR we can try to scatter them slightly around the destination if we don't have coords.
    # For a better UX, let's just show them in the sidebar and maybe a few key ones on map if we could.
    # For now, let's just pass the data to the template.

    plugins.Fullscreen().add_to(m)
    
    map_html = m._repr_html_()
    
    return templates.TemplateResponse("map.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "map_html": map_html,
        "recommendations": recommendations 
    })

