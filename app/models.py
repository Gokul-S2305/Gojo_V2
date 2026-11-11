from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import date, datetime


class TripUserLink(SQLModel, table=True):
    trip_id: Optional[int] = Field(default=None, foreign_key="trip.id", primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", primary_key=True)
    role: str = Field(default="member")  # "organizer" or "member"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: Optional[str] = None
    full_name: Optional[str] = None
    drive_connected: bool = Field(default=False)

    trips: List["Trip"] = Relationship(back_populates="users", link_model=TripUserLink)
    expenses: List["Expense"] = Relationship(back_populates="user")
    photos: List["Photo"] = Relationship(back_populates="user")
    messages: List["Message"] = Relationship(back_populates="user")
    documents: List["Document"] = Relationship(back_populates="user")
    push_subscriptions: List["PushSubscription"] = Relationship(back_populates="user")


class Trip(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    destination: str
    start_date: date
    end_date: date
    start_location: Optional[str] = None
    estimated_budget: Optional[float] = None
    join_code: str = Field(index=True, unique=True)
    drive_folder_id: Optional[str] = None
    notes: Optional[str] = None
    cover_image_url: Optional[str] = None

    users: List[User] = Relationship(back_populates="trips", link_model=TripUserLink)
    expenses: List["Expense"] = Relationship(back_populates="trip")
    photos: List["Photo"] = Relationship(back_populates="trip")
    messages: List["Message"] = Relationship(back_populates="trip")
    itinerary: List["ItineraryItem"] = Relationship(back_populates="trip")
    documents: List["Document"] = Relationship(back_populates="trip")
    recommendations: List["TripRecommendation"] = Relationship(back_populates="trip")


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float
    purpose: str
    category: str = Field(default="Other")  # Food, Transport, Hotel, Activity, Other
    trip_id: int = Field(foreign_key="trip.id")
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    trip: Trip = Relationship(back_populates="expenses")
    user: User = Relationship(back_populates="expenses")


class Photo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    user_id: int = Field(foreign_key="user.id")
    filename: str
    url: Optional[str] = None
    storage_id: Optional[str] = None
    media_type: str = Field(default="image")  # "image" or "video"
    caption: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    trip: "Trip" = Relationship(back_populates="photos")
    user: User = Relationship(back_populates="photos")


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    user_id: int = Field(foreign_key="user.id")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    trip: "Trip" = Relationship(back_populates="messages")
    user: User = Relationship(back_populates="messages")


class ItineraryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    day_number: int
    time: Optional[str] = None
    activity: str
    location: Optional[str] = None
    description: Optional[str] = None
    category: str = Field(default="Activity")  # Activity, Food, Hotel, Transport, Sightseeing
    order_index: int = Field(default=0)

    trip: Trip = Relationship(back_populates="itinerary")


class Document(SQLModel, table=True):
    """Hotel bookings, flight/bus/train tickets, car rentals, etc."""
    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    user_id: int = Field(foreign_key="user.id")
    doc_type: str  # "hotel", "flight", "bus", "train", "car", "other"
    title: str
    vendor: Optional[str] = None
    booking_ref: Optional[str] = None
    date_from: Optional[str] = None   # ISO date string
    date_to: Optional[str] = None     # ISO date string
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    notes: Optional[str] = None
    file_path: Optional[str] = None   # Uploaded attachment filename or relative path
    file_url: Optional[str] = None
    storage_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    trip: Trip = Relationship(back_populates="documents")
    user: User = Relationship(back_populates="documents")


class TripRecommendation(SQLModel, table=True):
    """Cached AI travel recommendations and plans per trip."""
    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id", index=True)
    budget_tier: str = Field(default="mid")  # "budget", "mid", "luxury"
    category: str = Field(default="all")  # "all", "hotels", "restaurants", "attractions", "plan"
    data_json: str  # JSON payload
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    trip: Optional[Trip] = Relationship(back_populates="recommendations")


class PushSubscription(SQLModel, table=True):
    """Web Push notification subscriptions."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    endpoint: str
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="push_subscriptions")
