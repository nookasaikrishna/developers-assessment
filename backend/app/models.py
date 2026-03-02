import uuid
from datetime import datetime, timezone
from typing import Optional


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (matches DB storage convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from pydantic import EmailStr, field_validator
from sqlmodel import Field, Relationship, SQLModel


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# WorkLog Payment Domain
# ---------------------------------------------------------------------------

class Remittance(SQLModel, table=True):
    """Single payout issued to a freelancer for a given billing period."""

    __tablename__ = "remittance"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    amount: float = Field(default=0.0)
    status: str = Field(default="COMPLETED", max_length=50, index=True)
    period_start: datetime = Field()
    period_end: datetime = Field()
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class WorkLog(SQLModel, table=True):
    """Container representing all time worked against a single task."""

    __tablename__ = "worklog"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_name: str = Field(max_length=255)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    status: str = Field(default="UNREMITTED", max_length=50, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    remittance_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="remittance.id", index=True, nullable=True
    )


class TimeEntry(SQLModel, table=True):
    """An individual time segment recorded by a freelancer against a WorkLog."""

    __tablename__ = "time_entry"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    worklog_id: uuid.UUID = Field(
        foreign_key="worklog.id", ondelete="CASCADE", index=True
    )
    description: str = Field(max_length=512)
    hours: float = Field()
    hourly_rate: float = Field()
    recorded_at: datetime = Field(default_factory=_utcnow, index=True)
    is_active: bool = Field(default=True)


# ---------------------------------------------------------------------------
# WorkLog API schemas
# ---------------------------------------------------------------------------

class TimeEntryResponse(SQLModel):
    id: uuid.UUID
    worklog_id: uuid.UUID
    description: str
    hours: float
    hourly_rate: float
    recorded_at: datetime
    is_active: bool
    amount: float  # hours * hourly_rate (computed by service layer)

    @field_validator("hours")
    @classmethod
    def validate_hours(cls, v: float) -> float:
        if v is None:
            raise ValueError("hours is required")
        if not isinstance(v, (int, float)):
            raise ValueError("hours must be a number")
        if v < 0:
            raise ValueError("hours cannot be negative")
        return float(v)

    @field_validator("hourly_rate")
    @classmethod
    def validate_hourly_rate(cls, v: float) -> float:
        if v is None:
            raise ValueError("hourly_rate is required")
        if not isinstance(v, (int, float)):
            raise ValueError("hourly_rate must be a number")
        if v < 0:
            raise ValueError("hourly_rate cannot be negative")
        return float(v)


class WorkLogResponse(SQLModel):
    id: uuid.UUID
    task_name: str
    user_id: uuid.UUID
    status: str
    created_at: datetime
    remittance_id: Optional[uuid.UUID]
    total_earnings: float
    freelancer_name: Optional[str]
    freelancer_email: str

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task_name cannot be empty")
        if len(v) > 255:
            raise ValueError("task_name too long")
        return v.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("REMITTED", "UNREMITTED"):
            raise ValueError("status must be REMITTED or UNREMITTED")
        return v


class WorkLogDetailResponse(WorkLogResponse):
    time_entries: list[TimeEntryResponse]


class WorkLogsResponse(SQLModel):
    data: list[WorkLogResponse]
    count: int


class WorkLogCreate(SQLModel):
    task_name: str

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        if v is None:
            raise ValueError("task_name is required")
        if not isinstance(v, str):
            raise ValueError("task_name must be a string")
        v = v.strip()
        if len(v) == 0:
            raise ValueError("task_name cannot be empty")
        if len(v) > 255:
            raise ValueError("task_name too long (max 255 chars)")
        return v


class TimeEntryCreate(SQLModel):
    description: str
    hours: float
    hourly_rate: float

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if v is None:
            raise ValueError("description is required")
        v = v.strip()
        if len(v) == 0:
            raise ValueError("description cannot be empty")
        if len(v) > 512:
            raise ValueError("description too long (max 512 chars)")
        return v

    @field_validator("hours")
    @classmethod
    def validate_hours(cls, v: float) -> float:
        if v is None:
            raise ValueError("hours is required")
        if not isinstance(v, (int, float)):
            raise ValueError("hours must be a number")
        if v <= 0:
            raise ValueError("hours must be greater than 0")
        if v > 24:
            raise ValueError("hours cannot exceed 24 per entry")
        return float(v)

    @field_validator("hourly_rate")
    @classmethod
    def validate_hourly_rate(cls, v: float) -> float:
        if v is None:
            raise ValueError("hourly_rate is required")
        if not isinstance(v, (int, float)):
            raise ValueError("hourly_rate must be a number")
        if v <= 0:
            raise ValueError("hourly_rate must be greater than 0")
        return float(v)


class RemittanceCreate(SQLModel):
    worklog_ids: list[uuid.UUID]
    period_start: datetime
    period_end: datetime

    @field_validator("worklog_ids")
    @classmethod
    def validate_worklog_ids(cls, v: list) -> list:
        if not v:
            raise ValueError("worklog_ids cannot be empty")
        return v

    @field_validator("period_start")
    @classmethod
    def validate_period_start(cls, v: datetime) -> datetime:
        if v is None:
            raise ValueError("period_start is required")
        return v

    @field_validator("period_end")
    @classmethod
    def validate_period_end(cls, v: datetime) -> datetime:
        if v is None:
            raise ValueError("period_end is required")
        return v


class RemittanceResponse(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    amount: float
    status: str
    period_start: datetime
    period_end: datetime
    created_at: datetime
    worklog_count: int
    freelancer_name: Optional[str]
    freelancer_email: str


class RemittancesResponse(SQLModel):
    data: list[RemittanceResponse]
    count: int
