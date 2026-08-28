from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class TicketPriority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class TicketStatus(StrEnum):
    new = "new"
    in_progress = "in_progress"
    resolved = "resolved"


class AssetType(StrEnum):
    desktop = "desktop"
    laptop = "laptop"
    printer = "printer"
    network_device = "network_device"


class AssetStatus(StrEnum):
    active = "active"
    maintenance = "maintenance"
    retired = "retired"


class AssetAvailability(StrEnum):
    unknown = "unknown"
    online = "online"
    offline = "offline"


class UserRole(StrEnum):
    employee = "employee"
    developer = "developer"
    specialist = "specialist"
    system_admin = "system_admin"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text)
    requester_email: Mapped[str] = mapped_column(String(255), index=True)
    priority: Mapped[TicketPriority] = mapped_column(Enum(TicketPriority), default=TicketPriority.normal)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.new)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType))
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.active)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    availability: Mapped[AssetAvailability] = mapped_column(Enum(AssetAvailability), default=AssetAvailability.unknown)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.specialist)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    avatar_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
