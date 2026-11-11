from fastapi import APIRouter, Request, Depends, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, ItineraryItem, Expense, Document
from app.auth_utils import get_current_user
from pathlib import Path
from datetime import date, datetime
import secrets

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# Exclude ambiguous characters: 0/O, 1/I/L
_JOIN_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


async def generate_join_code(session: AsyncSession) -> str:
    """Generate a unique 6-char join code with no ambiguous characters."""
    for _ in range(20):
        code = ''.join(secrets.choice(_JOIN_CODE_CHARS) for _ in range(6))
        result = await session.execute(select(Trip).where(Trip.join_code == code))
        if result.scalar_one_or_none() is None:
            return code
    raise RuntimeError("Failed to generate a unique join code after 20 attempts")


def _title(value: str | None) -> str | None:
    """Title-case a string, preserving None and stripping whitespace."""
    if not value:
        return None
    return value.strip().title()


def calculate_expense_split(members: list, expenses: list) -> tuple:
    """
    Computes per-person share and optimal settlement transactions.
    Returns: (total_expenses, per_person_share, balances_dict, settlements_list)
    """
    total = sum(e.get("amount", 0) for e in expenses)
    member_count = len(members)

    if member_count == 0 or total == 0:
        return total, 0.0, {}, []

    share = round(total / member_count, 2)
    member_map = {m.id: (m.full_name or m.email) for m in members}

    # Calculate paid per member
    paid_map = {m.id: 0.0 for m in members}
    for e in expenses:
        uid = e.get("user_id")
        if uid in paid_map:
            paid_map[uid] += e.get("amount", 0.0)

    # Calculate net balance: paid - share
    # Positive = owed money (creditor), Negative = owes money (debtor)
    balances = {}
    debtors = []   # (amount_owed, uid, name)
    creditors = [] # (amount_owed_to, uid, name)

    for uid, name in member_map.items():
        paid = paid_map[uid]
        net = round(paid - share, 2)
        balances[uid] = {
            "name": name,
            "paid": round(paid, 2),
            "net": net,
        }
        if net < -0.01:
            debtors.append([-net, uid, name])
        elif net > 0.01:
            creditors.append([net, uid, name])

    # Greedy matching for minimal settlements
    settlements = []
    d_idx = 0
    c_idx = 0

    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor_amt, d_id, d_name = debtors[d_idx]
        creditor_amt, c_id, c_name = creditors[c_idx]

        settle_amt = min(debtor_amt, creditor_amt)
        if settle_amt > 0.01:
            settlements.append({
                "from_id": d_id,
                "from_name": d_name,
                "to_id": c_id,
                "to_name": c_name,
                "amount": round(settle_amt, 2),
            })

        debtors[d_idx][0] -= settle_amt
        creditors[c_idx][0] -= settle_amt

        if debtors[d_idx][0] <= 0.01:
            d_idx += 1
        if creditors[c_idx][0] <= 0.01:
            c_idx += 1

    return total, share, balances, settlements


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    statement = (
        select(Trip)
        .join(TripUserLink)
        .where(TripUserLink.user_id == user.id)
        .order_by(Trip.start_date.asc())
    )
    result = await session.execute(statement)
    trips = result.scalars().all()

    today = date.today()
    upcoming_trips = [t for t in trips if t.end_date >= today]
    past_trips = [t for t in trips if t.end_date < today]

    next_trip = None
    countdown_days = None
    if upcoming_trips:
        next_trip = upcoming_trips[0]
        countdown_days = (next_trip.start_date - today).days

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "trips": trips,
        "upcoming_trips": upcoming_trips,
        "past_trips": past_trips,
        "next_trip": next_trip,
        "countdown_days": countdown_days,
        "today": today,
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
        user_db.full_name = full_name.strip()
        session.add(user_db)
        await session.commit()

    return RedirectResponse("/dashboard?msg=Profile+updated", status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Trip Creation & Joining
# ---------------------------------------------------------------------------

@router.post("/trip/create")
async def create_trip(
    request: Request,
    user: User = Depends(get_current_user),
    trip_name: str = Form(...),
    destination: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_location: str = Form(None),
    estimated_budget: float = Form(None),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    join_code = await generate_join_code(session)
    s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    e_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    cleaned_name = _title(trip_name) or trip_name.strip()
    cleaned_dest = _title(destination) or destination.strip()
    cleaned_start = _title(start_location) if start_location else None

    new_trip = Trip(
        name=cleaned_name,
        destination=cleaned_dest,
        start_date=s_date,
        end_date=e_date,
        start_location=cleaned_start,
        estimated_budget=estimated_budget,
        join_code=join_code,
    )

    if user.drive_connected:
        google_access_token = request.session.get('google_access_token')
        if google_access_token:
            try:
                from app.drive_service import get_drive_service, find_or_create_parent_folder, create_trip_folder
                service = get_drive_service(google_access_token)
                parent_id = await find_or_create_parent_folder(service)
                folder_id = await create_trip_folder(service, cleaned_name, parent_id)
                new_trip.drive_folder_id = folder_id
            except Exception as e:
                logger.warning(f"Drive folder creation failed: {e}")

    session.add(new_trip)
    await session.commit()
    await session.refresh(new_trip)

    link = TripUserLink(trip_id=new_trip.id, user_id=user.id, role="organizer")
    session.add(link)
    await session.commit()

    return RedirectResponse(f"/trip/{new_trip.id}?msg=Trip+created+successfully", status_code=status.HTTP_302_FOUND)


@router.post("/trip/join")
async def join_trip(
    request: Request,
    user: User = Depends(get_current_user),
    join_code: str = Form(...),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    clean_code = join_code.strip().upper()
    statement = select(Trip).where(Trip.join_code == clean_code)
    result = await session.execute(statement)
    trip = result.scalar_one_or_none()

    if not trip:
        return RedirectResponse("/dashboard?error=Invalid+join+code", status_code=status.HTTP_302_FOUND)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip.id,
        TripUserLink.user_id == user.id
    )
    existing_link = await session.execute(link_statement)
    if existing_link.scalar_one_or_none():
        return RedirectResponse(f"/trip/{trip.id}?msg=Already+a+member", status_code=status.HTTP_302_FOUND)

    link = TripUserLink(trip_id=trip.id, user_id=user.id, role="member")
    session.add(link)
    await session.commit()

    return RedirectResponse(f"/trip/{trip.id}?msg=Welcome+to+{trip.name}", status_code=status.HTTP_302_FOUND)


@router.get("/join/{join_code}")
async def quick_join(
    join_code: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Direct invite link: /join/CODE."""
    clean_code = join_code.strip().upper()
    if not user:
        return RedirectResponse(f"/login?next=/join/{clean_code}", status_code=status.HTTP_302_FOUND)

    statement = select(Trip).where(Trip.join_code == clean_code)
    result = await session.execute(statement)
    trip = result.scalar_one_or_none()

    if not trip:
        raise HTTPException(status_code=404, detail="Invalid invite link")

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip.id,
        TripUserLink.user_id == user.id
    )
    existing_link = await session.execute(link_statement)
    if not existing_link.scalar_one_or_none():
        link = TripUserLink(trip_id=trip.id, user_id=user.id, role="member")
        session.add(link)
        await session.commit()

    return RedirectResponse(f"/trip/{trip.id}?msg=Joined+{trip.name}", status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Trip Management (Edit / Delete)
# ---------------------------------------------------------------------------

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

    if not link:
        raise HTTPException(status_code=404, detail="Trip not found")
    if link.role != "organizer":
        raise HTTPException(status_code=403, detail="Organizer permission required to delete trip")

    trip = await session.get(Trip, trip_id)
    if trip:
        await session.delete(trip)
        await session.commit()

    return RedirectResponse("/dashboard?msg=Trip+deleted", status_code=status.HTTP_302_FOUND)


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

    if not link:
        raise HTTPException(status_code=404, detail="Trip not found")
    if link.role != "organizer":
        raise HTTPException(status_code=403, detail="Organizer permission required to edit trip")

    trip = await session.get(Trip, trip_id)
    if trip:
        trip.name = _title(trip_name) or trip_name.strip()
        trip.destination = _title(destination) or destination.strip()
        trip.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        trip.end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        trip.start_location = _title(start_location) if start_location else None
        trip.estimated_budget = estimated_budget
        trip.notes = notes.strip() if notes else None

        session.add(trip)
        await session.commit()

    return RedirectResponse(f"/trip/{trip_id}?msg=Trip+details+updated", status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Trip Detail View
# ---------------------------------------------------------------------------

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
        raise HTTPException(status_code=404, detail="Trip not found")

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    current_user_link = link_result.scalar_one_or_none()

    if not current_user_link:
        raise HTTPException(status_code=404, detail="Trip not found")

    is_organizer = current_user_link.role == "organizer"

    # Get members with roles
    members_statement = select(TripUserLink, User).join(
        User, TripUserLink.user_id == User.id
    ).where(TripUserLink.trip_id == trip_id)
    members_result = await session.execute(members_statement)
    members_data = members_result.all()

    all_members = [m[1] for m in members_data]
    organizers = [m[1] for m in members_data if m[0].role == "organizer"]
    regular_members = [m[1] for m in members_data if m[0].role == "member"]

    # Get Itinerary sorted by day and time/order
    itinerary_statement = (
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.day_number, ItineraryItem.order_index, ItineraryItem.time)
    )
    itinerary_result = await session.execute(itinerary_statement)
    itinerary_items = itinerary_result.scalars().all()

    # Group itinerary by day
    duration = (trip.end_date - trip.start_date).days + 1
    itinerary_by_day = {day: [] for day in range(1, duration + 1)}
    for item in itinerary_items:
        if item.day_number in itinerary_by_day:
            itinerary_by_day[item.day_number].append(item)
        else:
            itinerary_by_day.setdefault(item.day_number, []).append(item)

    # Get Expenses
    expenses_statement = select(Expense, User).join(
        User, Expense.user_id == User.id
    ).where(Expense.trip_id == trip_id).order_by(Expense.created_at.desc())
    expenses_result = await session.execute(expenses_statement)
    expenses_with_users = expenses_result.all()

    expenses_data = [
        {
            "id": exp.id,
            "purpose": exp.purpose,
            "amount": exp.amount,
            "category": exp.category,
            "created_at": exp.created_at,
            "user_id": exp.user_id,
            "user_name": exp_user.full_name or exp_user.email,
        }
        for exp, exp_user in expenses_with_users
    ]

    total_expenses, share, balances, settlements = calculate_expense_split(all_members, expenses_data)

    # Get Documents
    docs_statement = select(Document).where(Document.trip_id == trip_id).order_by(Document.created_at.desc())
    docs_result = await session.execute(docs_statement)
    documents = docs_result.scalars().all()

    return templates.TemplateResponse("trip_detail.html", {
        "request": request,
        "user": user,
        "trip": trip,
        "organizers": organizers,
        "members": regular_members,
        "all_members": all_members,
        "itinerary": itinerary_items,
        "itinerary_by_day": itinerary_by_day,
        "is_organizer": is_organizer,
        "expenses": expenses_data,
        "total_expenses": total_expenses,
        "per_person_share": share,
        "member_balances": balances,
        "settlements": settlements,
        "duration": duration,
        "documents": documents,
    })


# ---------------------------------------------------------------------------
# Itinerary Actions
# ---------------------------------------------------------------------------

@router.post("/trip/{trip_id}/itinerary/add")
async def add_itinerary_item(
    request: Request,
    trip_id: int,
    day_number: int = Form(...),
    time: str = Form(None),
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

    if not link:
        raise HTTPException(status_code=404, detail="Trip not found")
    if link.role != "organizer":
        raise HTTPException(status_code=403, detail="Organizer permission required to modify itinerary")

    new_item = ItineraryItem(
        trip_id=trip_id,
        day_number=day_number,
        time=time,
        activity=activity.strip(),
        location=location.strip() if location else None,
        description=description.strip() if description else None,
        category=category
    )
    session.add(new_item)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}#itinerary", status_code=status.HTTP_302_FOUND)


@router.post("/trip/{trip_id}/itinerary/{item_id}/edit")
async def edit_itinerary_item(
    trip_id: int,
    item_id: int,
    request: Request,
    day_number: int = Form(...),
    time: str = Form(None),
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

    if not link:
        raise HTTPException(status_code=404, detail="Trip not found")
    if link.role != "organizer":
        raise HTTPException(status_code=403, detail="Organizer permission required to edit itinerary")

    item = await session.get(ItineraryItem, item_id)
    if item and item.trip_id == trip_id:
        item.day_number = day_number
        item.time = time
        item.activity = activity.strip()
        item.location = location.strip() if location else None
        item.description = description.strip() if description else None
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

    if not link:
        raise HTTPException(status_code=404, detail="Trip not found")
    if link.role != "organizer":
        raise HTTPException(status_code=403, detail="Organizer permission required to delete itinerary items")

    item = await session.get(ItineraryItem, item_id)
    if item and item.trip_id == trip_id:
        await session.delete(item)
        await session.commit()

    return RedirectResponse(f"/trip/{trip_id}#itinerary", status_code=status.HTTP_302_FOUND)


@router.post("/api/trip/{trip_id}/itinerary/reorder")
async def reorder_itinerary(
    trip_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """API for Drag & Drop Itinerary sorting."""
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()

    if not link or link.role != "organizer":
        return JSONResponse({"error": "Organizer permission required"}, status_code=403)

    data = await request.json()
    items_order = data.get("items", [])  # [{"id": 1, "day_number": 1, "order_index": 0}, ...]

    for item_data in items_order:
        item = await session.get(ItineraryItem, item_data["id"])
        if item and item.trip_id == trip_id:
            item.day_number = item_data.get("day_number", item.day_number)
            item.order_index = item_data.get("order_index", 0)
            session.add(item)

    await session.commit()
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

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
        raise HTTPException(status_code=404, detail="Trip not found")

    new_expense = Expense(
        trip_id=trip_id,
        user_id=user.id,
        purpose=purpose.strip(),
        amount=amount,
        category=category
    )
    session.add(new_expense)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}#expenses", status_code=status.HTTP_302_FOUND)


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
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense.user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot edit expense created by another user")

    expense.purpose = purpose.strip()
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
        raise HTTPException(status_code=404, detail="Expense not found")

    # Check if user is creator or organizer
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    link = link_result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Trip not found")

    if expense.user_id != user.id and link.role != "organizer":
        raise HTTPException(status_code=403, detail="Only creator or organizer can delete expense")

    await session.delete(expense)
    await session.commit()

    return RedirectResponse(f"/trip/{trip_id}#expenses", status_code=status.HTTP_302_FOUND)
