from fastapi import APIRouter, Request, Depends, Form, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, ItineraryItem, Expense
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

    statement = select(Trip).join(TripUserLink).where(TripUserLink.user_id == user.id)
    result = await session.execute(statement)
    trips = result.scalars().all()

    from datetime import date
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, "trips": trips, "today": date.today()
    })


@router.post("/profile/update")
async def update_profile(
    request: Request,
    user: User = Depends(get_current_user),
    full_name: str = Form(...),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
        
    user_db = await session.get(User, user.id)
    if user_db:
        user_db.full_name = full_name
        session.add(user_db)
        await session.commit()
        
    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)


@router.post("/trip/create")
async def create_trip(
    request: Request,
    user: User = Depends(get_current_user),
    trip_name: str = Form(...),
    destination: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_location: str = Form(None),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    join_code = generate_join_code()
    from datetime import datetime

    s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    e_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    new_trip = Trip(
        name=trip_name,
        destination=destination,
        start_date=s_date,
        end_date=e_date,
        start_location=start_location,
        join_code=join_code
    )

    if user.drive_connected:
        google_access_token = request.session.get('google_access_token')
        if google_access_token:
            try:
                from app.drive_service import get_drive_service, find_or_create_parent_folder, create_trip_folder
                service = get_drive_service(google_access_token)
                parent_id = await find_or_create_parent_folder(service)
                folder_id = await create_trip_folder(service, trip_name, parent_id)
                new_trip.drive_folder_id = folder_id
            except Exception as e:
                print(f"Drive folder creation failed: {e}")

    session.add(new_trip)
    await session.commit()
    await session.refresh(new_trip)

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
        return RedirectResponse("/dashboard?error=Invalid+Code", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip.id,
        TripUserLink.user_id == user.id
    )
    existing_link = await session.execute(link_statement)
    if existing_link.scalar_one_or_none():
        return RedirectResponse("/dashboard?msg=Already+joined", status_code=status.HTTP_302_FOUND)

    link = TripUserLink(trip_id=trip.id, user_id=user.id)
    session.add(link)
    await session.commit()

    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/delete")
async def delete_trip(
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()

    if not link or link.role != "organizer":
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    trip = await session.get(Trip, trip_id)
    if trip:
        await session.delete(trip)
        await session.commit()

    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/edit")
async def edit_trip(
    trip_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    trip_name: str = Form(...),
    destination: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_location: str = Form(None),
    estimated_budget: float = Form(None),
    notes: str = Form(None),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()

    if not link or link.role != "organizer":
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    trip = await session.get(Trip, trip_id)
    if trip:
        from datetime import datetime
        trip.name = trip_name
        trip.destination = destination
        trip.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        trip.end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        trip.start_location = start_location
        trip.estimated_budget = estimated_budget
        trip.notes = notes
        
        session.add(trip)
        await session.commit()

    # If referer is dashboard, return to dashboard, else trip detail
    referer = request.headers.get("referer", "/dashboard")
    return RedirectResponse(referer, status_code=status.HTTP_302_FOUND)


@router.get("/trip/{trip_id}", response_class=HTMLResponse)
async def trip_detail(
    request: Request,
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()

    if not trip:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    current_user_link = link_result.scalar_one_or_none()

    if not current_user_link:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    is_organizer = current_user_link.role == "organizer"

    # Get members with roles via JOIN (fixes N+1)
    from sqlalchemy import join as sa_join
    from app.models import User as UserModel
    members_statement = select(TripUserLink, UserModel).join(
        UserModel, TripUserLink.user_id == UserModel.id
    ).where(TripUserLink.trip_id == trip_id)
    members_result = await session.execute(members_statement)
    members_data = members_result.all()

    organizers = [m[1] for m in members_data if m[0].role == "organizer"]
    members = [m[1] for m in members_data if m[0].role == "member"]

    # Get Itinerary
    itinerary_statement = select(ItineraryItem).where(
        ItineraryItem.trip_id == trip_id
    ).order_by(ItineraryItem.day_number, ItineraryItem.time)
    itinerary_result = await session.execute(itinerary_statement)
    itinerary_items = itinerary_result.scalars().all()

    # Get expenses with user info via JOIN (fixes N+1)
    expenses_statement = select(Expense, UserModel).join(
        UserModel, Expense.user_id == UserModel.id
    ).where(Expense.trip_id == trip_id).order_by(Expense.created_at.desc())
    expenses_result = await session.execute(expenses_statement)
    expenses_with_users = expenses_result.all()

    # Bundle expense + user into a dict-like structure
    expenses_data = []
    for exp, exp_user in expenses_with_users:
        expenses_data.append({
            "id": exp.id,
            "purpose": exp.purpose,
            "amount": exp.amount,
            "category": exp.category,
            "created_at": exp.created_at,
            "user_id": exp.user_id,
            "user_name": exp_user.full_name or exp_user.email,
        })

    total_expenses = sum(e["amount"] for e in expenses_data)
    duration = (trip.end_date - trip.start_date).days + 1

    # Get documents
    from app.models import Document
    docs_statement = select(Document).where(Document.trip_id == trip_id).order_by(Document.created_at.desc())
    docs_result = await session.execute(docs_statement)
    documents = docs_result.scalars().all()

    return templates.TemplateResponse("trip_detail.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "organizers": organizers,
        "members": members,
        "itinerary": itinerary_items,
        "is_organizer": is_organizer,
        "expenses": expenses_data,
        "total_expenses": total_expenses,
        "duration": duration,
        "documents": documents,
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
    category: str = Form("Activity"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()

    if not link or link.role != "organizer":
        return RedirectResponse(f"/trip/{trip_id}?error=Unauthorized", status_code=status.HTTP_302_FOUND)

    new_item = ItineraryItem(
        trip_id=trip_id,
        day_number=day_number,
        time=time,
        activity=activity,
        location=location,
        description=description,
        category=category
    )
    session.add(new_item)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/itinerary/{item_id}/edit")
async def edit_itinerary_item(
    trip_id: int,
    item_id: int,
    request: Request,
    day_number: int = Form(...),
    time: str = Form(...),
    activity: str = Form(...),
    location: str = Form(None),
    description: str = Form(None),
    category: str = Form("Activity"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

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
        item.day_number = day_number
        item.time = time
        item.activity = activity
        item.location = location
        item.description = description
        item.category = category
        session.add(item)
        await session.commit()

    return RedirectResponse(f"/trip/{trip_id}#itinerary", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/itinerary/{item_id}/delete")
async def delete_itinerary_item(
    trip_id: int,
    item_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

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
    category: str = Form("Other"),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    new_expense = Expense(
        trip_id=trip_id,
        user_id=user.id,
        purpose=purpose,
        amount=amount,
        category=category
    )
    session.add(new_expense)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/expense/{expense_id}/edit")
async def edit_expense(
    request: Request,
    trip_id: int,
    expense_id: int,
    user: User = Depends(get_current_user),
    purpose: str = Form(...),
    amount: float = Form(...),
    category: str = Form("Other"),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    expense_statement = select(Expense).where(Expense.id == expense_id, Expense.trip_id == trip_id)
    expense_result = await session.execute(expense_statement)
    expense = expense_result.scalar_one_or_none()

    if not expense:
        return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

    if expense.user_id != user.id:
        return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

    expense.purpose = purpose
    expense.amount = amount
    expense.category = category
    session.add(expense)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}#expenses", status_code=status.HTTP_302_FOUND)


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

    expense_statement = select(Expense).where(Expense.id == expense_id, Expense.trip_id == trip_id)
    expense_result = await session.execute(expense_statement)
    expense = expense_result.scalar_one_or_none()

    if not expense:
        return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

    if expense.user_id != user.id:
        return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)

    await session.delete(expense)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}", status_code=status.HTTP_302_FOUND)
