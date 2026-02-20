from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: str
    password_hash: str
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    items: list["OrderItem"] = Relationship(back_populates="user")


class Restaurant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    menu_items: list["MenuItem"] = Relationship(back_populates="restaurant", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class MenuItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    name: str
    price_eur: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    restaurant: Restaurant = Relationship(back_populates="menu_items")


class OrderSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str  # e.g. "Lunch – Pizza Service"
    restaurant_id: Optional[int] = Field(default=None, foreign_key="restaurant.id")
    restaurant: str  # kept for display / legacy
    restaurant_url: Optional[str] = None
    notes: Optional[str] = None

    deadline_at: datetime
    status: str = "open"  # open | closed
    created_by_user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

    items: list["OrderItem"] = Relationship(back_populates="session")


class OrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="ordersession.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    item_name: str
    quantity: int = 1
    price_eur: Optional[float] = None
    notes: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    session: OrderSession = Relationship(back_populates="items")
    user: User = Relationship(back_populates="items")
