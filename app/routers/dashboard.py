from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, ItineraryItem
from app.auth_utils import get_current_user
from pathlib import Path
import secrets
import string

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

def generate_join_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    # Refresh user to get relationships (trips)
    # Note: async loading of relationships requires explicit query or eager loading. 
    # For simplicity, we query trips via link table.
    # But SQLModel relationships should work if attached to session.
    # Let's do a direct select for trips.
    
    # We need to fetch trips associated with user
    # This involves a join or select.
    # Workaround for async relationship loading if lazy='select' (default) is problematic:
    # We'll select Trip where Trip.users contains user... 
    # But many-to-many is tricky in async without eager loading options.
    pass  
    
    # Let's try explicit join
    statement = select(Trip).join(TripUserLink).where(TripUserLink.user_id == user.id)
    result = await session.execute(statement)
    trips = result.scalars().all()

    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "trips": trips})

@router.post("/trip/create")
async def create_trip(
    request: Request,
    user: User = Depends(get_current_user),
    trip_name: str = Form(...),
    destination: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_location: str = Form(None),
    # estimated_budget: float = Form(None), # Auto-calculated
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
        
    # Create trip
    join_code = generate_join_code()
    from datetime import datetime
    
    # Basic date parsing
    s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    # Auto-calculate estimated budget
    duration = (e_date - s_date).days + 1
    daily_avg_cost = 3000 # Hotel + Food
    base_travel_cost = 5000 # Flight/Train
    estimated_budget = (duration * daily_avg_cost) + base_travel_cost
    
    new_trip = Trip(
        name=trip_name,
        destination=destination,
        start_date=s_date,
        end_date=e_date,
        start_location=start_location,
        estimated_budget=estimated_budget,
        join_code=join_code
    )
    session.add(new_trip)
    await session.commit()
    await session.refresh(new_trip)
    
    # Link user to trip
    # Link user to trip as Organizer
    link = TripUserLink(trip_id=new_trip.id, user_id=user.id, role="organizer")
    session.add(link)
    await session.commit()
    
    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

@router.post("/trip/join")
async def join_trip(
    request: Request,
    user: User = Depends(get_current_user),
    join_code: str = Form(...),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    statement = select(Trip).where(Trip.join_code == join_code.upper())
    result = await session.execute(statement)
    trip = result.scalar_one_or_none()
    
    if not trip:
        # Ideally show error, but redirecting for now
        return RedirectResponse("/dashboard?error=Invalid Code", status_code=status.HTTP_302_FOUND)
    
    # Check if already joined
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip.id, 
        TripUserLink.user_id == user.id
    )
    existing_link = await session.execute(link_statement)
    if existing_link.scalar_one_or_none():
         return RedirectResponse("/dashboard?msg=Already joined", status_code=status.HTTP_302_FOUND)

    link = TripUserLink(trip_id=trip.id, user_id=user.id)
    session.add(link)
    await session.commit()
    
    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

@router.get("/trip/{trip_id}", response_class=HTMLResponse)
async def trip_detail(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    # Get trip
    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()
    
    if not trip:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    
    # Check if user is member of trip
    # Check if user is member of trip & get role
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    current_user_link = link_result.scalar_one_or_none()
    
    if not current_user_link:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    
    is_organizer = current_user_link.role == "organizer"
    
    # Get all members with roles
    # returning (TripUserLink, User)
    members_statement = select(TripUserLink, User).join(User).where(TripUserLink.trip_id == trip_id)
    members_result = await session.execute(members_statement)
    members_data = members_result.all()
    
    # Group by role
    organizers = [m[1] for m in members_data if m[0].role == "organizer"]
    members = [m[1] for m in members_data if m[0].role == "member"] 

    # Get Itinerary
    itinerary_statement = select(ItineraryItem).where(ItineraryItem.trip_id == trip_id).order_by(ItineraryItem.day_number, ItineraryItem.time)
    itinerary_result = await session.execute(itinerary_statement)
    itinerary_items = itinerary_result.scalars().all()
    
    # Get all expenses with user info
    from app.models import Expense
    expenses_statement = select(Expense).where(Expense.trip_id == trip_id).order_by(Expense.created_at.desc())
    expenses_result = await session.execute(expenses_statement)
    expenses = expenses_result.scalars().all()
    
    # Load user relationship for each expense
    for expense in expenses:
        await session.refresh(expense, ["user"])
    
    # Calculate total
    total_expenses = sum(expense.amount for expense in expenses)
    
    # Calculate duration
    duration = (trip.end_date - trip.start_date).days + 1
    
    return templates.TemplateResponse("trip_detail.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "organizers": organizers,
        "members": members,
        "itinerary": itinerary_items,
        "is_organizer": is_organizer,
        "expenses": expenses,
        "total_expenses": total_expenses,
        "duration": duration
    })

@router.post("/trip/{trip_id}/itinerary/add")
async def add_itinerary_item(
    request: Request,
    trip_id: int,
    day_number: int = Form(...),
    time: str = Form(...),
    activity: str = Form(...),
    location: str = Form(None),
    description: str = Form(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
        
    # Check permissions (organizer only)
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()
    
    if not link or link.role != "organizer":
        # Unauthorized
        return RedirectResponse(f"/trip/{trip_id}?error=Unauthorized", status_code=status.HTTP_302_FOUND)
        
    new_item = ItineraryItem(
        trip_id=trip_id,
        day_number=day_number,
        time=time,
        activity=activity,
        location=location,
        description=description
    )
    session.add(new_item)
    await session.commit()
    
    return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

@router.post("/trip/{trip_id}/itinerary/{item_id}/delete")
async def delete_itinerary_item(
    trip_id: int,
    item_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
        
    # Check permissions (organizer only)
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()
    
    if not link or link.role != "organizer":
        return RedirectResponse(f"/trip/{trip_id}?error=Unauthorized", status_code=status.HTTP_302_FOUND)

    item = await session.get(ItineraryItem, item_id)
    if item and item.trip_id == trip_id:
        await session.delete(item)
        await session.commit()
        
    return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

@router.post("/trip/{trip_id}/expense")
async def create_expense(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    purpose: str = Form(...),
    amount: float = Form(...),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    # Verify user is member of trip
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    
    # Create expense
    from app.models import Expense
    new_expense = Expense(
        trip_id=trip_id,
        user_id=user.id,
        purpose=purpose,
        amount=amount
    )
    session.add(new_expense)
    await session.commit()
    
    return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

@router.post("/trip/{trip_id}/expense/{expense_id}/delete")
async def delete_expense(
    request: Request,
    trip_id: int,
    expense_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    
    # Get expense
    from app.models import Expense
    expense_statement = select(Expense).where(Expense.id == expense_id, Expense.trip_id == trip_id)
    expense_result = await session.execute(expense_statement)
    expense = expense_result.scalar_one_or_none()
    
    if not expense:
        return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)
    
    # Only allow user who created expense to delete it
    if expense.user_id != user.id:
        return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)
    
    await session.delete(expense)
    await session.commit()
    
    return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

