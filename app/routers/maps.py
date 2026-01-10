from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink
from app.auth_utils import get_current_user
from pathlib import Path
import folium
from folium import plugins

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# Famous places database (fallback when no API is available)
FAMOUS_PLACES = {
    "goa": [
        {"name": "Baga Beach", "lat": 15.5559, "lng": 73.7516, "type": "Beach"},
        {"name": "Calangute Beach", "lat": 15.5438, "lng": 73.7626, "type": "Beach"},
        {"name": "Fort Aguada", "lat": 15.4909, "lng": 73.7730, "type": "Historical"},
        {"name": "Basilica of Bom Jesus", "lat": 15.5008, "lng": 73.9114, "type": "Religious"},
        {"name": "Dudhsagar Falls", "lat": 15.3144, "lng": 74.3144, "type": "Nature"},
    ],
    "delhi": [
        {"name": "India Gate", "lat": 28.6129, "lng": 77.2295, "type": "Monument"},
        {"name": "Red Fort", "lat": 28.6562, "lng": 77.2410, "type": "Historical"},
        {"name": "Qutub Minar", "lat": 28.5244, "lng": 77.1855, "type": "Historical"},
        {"name": "Lotus Temple", "lat": 28.5535, "lng": 77.2588, "type": "Religious"},
        {"name": "Humayun's Tomb", "lat": 28.5933, "lng": 77.2507, "type": "Historical"},
    ],
    "mumbai": [
        {"name": "Gateway of India", "lat": 18.9220, "lng": 72.8347, "type": "Monument"},
        {"name": "Marine Drive", "lat": 18.9432, "lng": 72.8236, "type": "Scenic"},
        {"name": "Elephanta Caves", "lat": 18.9633, "lng": 72.9315, "type": "Historical"},
        {"name": "Haji Ali Dargah", "lat": 18.9826, "lng": 72.8089, "type": "Religious"},
        {"name": "Juhu Beach", "lat": 19.0990, "lng": 72.8265, "type": "Beach"},
    ],
    "jaipur": [
        {"name": "Hawa Mahal", "lat": 26.9239, "lng": 75.8267, "type": "Historical"},
        {"name": "Amber Fort", "lat": 26.9855, "lng": 75.8513, "type": "Historical"},
        {"name": "City Palace", "lat": 26.9258, "lng": 75.8237, "type": "Historical"},
        {"name": "Jantar Mantar", "lat": 26.9246, "lng": 75.8246, "type": "Historical"},
        {"name": "Nahargarh Fort", "lat": 26.9394, "lng": 75.8150, "type": "Historical"},
    ],
    "bangalore": [
        {"name": "Lalbagh Botanical Garden", "lat": 12.9507, "lng": 77.5848, "type": "Nature"},
        {"name": "Cubbon Park", "lat": 12.9762, "lng": 77.5929, "type": "Nature"},
        {"name": "Bangalore Palace", "lat": 12.9980, "lng": 77.5920, "type": "Historical"},
        {"name": "ISKCON Temple", "lat": 13.0096, "lng": 77.5511, "type": "Religious"},
        {"name": "Vidhana Soudha", "lat": 12.9794, "lng": 77.5912, "type": "Monument"},
    ],
    "kerala": [
        {"name": "Munnar Tea Gardens", "lat": 10.0889, "lng": 77.0595, "type": "Nature"},
        {"name": "Alleppey Backwaters", "lat": 9.4981, "lng": 76.3388, "type": "Nature"},
        {"name": "Kovalam Beach", "lat": 8.4004, "lng": 76.9790, "type": "Beach"},
        {"name": "Periyar Wildlife Sanctuary", "lat": 9.4647, "lng": 77.2350, "type": "Nature"},
        {"name": "Fort Kochi", "lat": 9.9654, "lng": 76.2424, "type": "Historical"},
    ],
}

# City coordinates for map centering
CITY_COORDS = {
    "goa": (15.2993, 74.1240),
    "delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "jaipur": (26.9124, 75.7873),
    "bangalore": (12.9716, 77.5946),
    "kerala": (10.8505, 76.2711),
}

def get_places_for_destination(destination: str):
    """Get famous places for a destination city."""
    dest_lower = destination.lower().strip()
    
    # Try exact match first
    if dest_lower in FAMOUS_PLACES:
        return FAMOUS_PLACES[dest_lower]
    
    # Try partial match
    for city, places in FAMOUS_PLACES.items():
        if city in dest_lower or dest_lower in city:
            return places
    
    # Default fallback - return generic marker at city center
    return []

def get_city_coordinates(destination: str):
    """Get coordinates for a city to center the map."""
    dest_lower = destination.lower().strip()
    
    # Try exact match
    if dest_lower in CITY_COORDS:
        return CITY_COORDS[dest_lower]
    
    # Try partial match
    for city, coords in CITY_COORDS.items():
        if city in dest_lower or dest_lower in city:
            return coords
    
    # Default to India center
    return (20.5937, 78.9629)

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
    
    # Check if user is member
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=302)
    
    # Get coordinates and places
    center_coords = get_city_coordinates(trip.destination)
    places = get_places_for_destination(trip.destination)
    
    # Create map
    trip_map = folium.Map(
        location=center_coords,
        zoom_start=12 if places else 6,
        tiles="OpenStreetMap"
    )
    
    # Add destination marker
    folium.Marker(
        center_coords,
        popup=f"<b>{trip.destination}</b><br>Your destination!",
        tooltip=trip.destination,
        icon=folium.Icon(color="red", icon="star", prefix="fa")
    ).add_to(trip_map)
    
    # Add place markers
    for place in places:
        # Color code by type
        color_map = {
            "Beach": "blue",
            "Historical": "orange",
            "Religious": "purple",
            "Nature": "green",
            "Monument": "red",
            "Scenic": "lightblue"
        }
        color = color_map.get(place["type"], "gray")
        
        folium.Marker(
            [place["lat"], place["lng"]],
            popup=f"<b>{place['name']}</b><br>{place['type']}",
            tooltip=place["name"],
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(trip_map)
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(trip_map)
    
    # Get map HTML
    map_html = trip_map._repr_html_()
    
    return templates.TemplateResponse("map.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "places": places,
        "map_html": map_html
    })
