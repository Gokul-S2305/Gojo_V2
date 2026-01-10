from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import date, datetime

class TripUserLink(SQLModel, table=True):
    trip_id: Optional[int] = Field(default=None, foreign_key="trip.id", primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", primary_key=True)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    full_name: Optional[str] = None
    
    trips: List["Trip"] = Relationship(back_populates="users", link_model=TripUserLink)
    expenses: List["Expense"] = Relationship(back_populates="user")
    photos: List["Photo"] = Relationship(back_populates="user")
    messages: List["Message"] = Relationship(back_populates="user")

class Trip(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    destination: str
    start_date: date
    end_date: date
    join_code: str = Field(index=True, unique=True)
    
    users: List[User] = Relationship(back_populates="trips", link_model=TripUserLink)
    expenses: List["Expense"] = Relationship(back_populates="trip")
    photos: List["Photo"] = Relationship(back_populates="trip")
    messages: List["Message"] = Relationship(back_populates="trip")

class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float
    purpose: str
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


