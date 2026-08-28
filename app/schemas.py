from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from .models import AssetAvailability, AssetStatus, AssetType, TicketPriority, TicketStatus, UserRole


class TicketCreate(BaseModel):
    title: str = Field(min_length=5, max_length=160, examples=["Не печатает принтер на 3 этаже"])
    description: str = Field(min_length=10, examples=["Принтер показывает статус offline после перезагрузки ПК."])
    priority: TicketPriority = TicketPriority.normal


class TicketRead(TicketCreate):
    id: int
    requester_email: EmailStr
    status: TicketStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class RegisterRequest(LoginRequest):
    full_name: str = Field(min_length=2, max_length=120)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    specialist_email: EmailStr
    user_role: UserRole
    full_name: str
    avatar_path: str | None = None


class ProfileRead(BaseModel):
    email: EmailStr
    role: UserRole
    full_name: str
    avatar_path: str | None = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: UserRole


class AssetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120, examples=["ALM-PRN-03"])
    asset_type: AssetType
    ip_address: str | None = Field(default=None, examples=["192.168.10.33"])
    owner_email: EmailStr | None = None
    location: str | None = Field(default=None, max_length=120, examples=["3 этаж, бухгалтерия"])


class AssetRead(AssetCreate):
    id: int
    status: AssetStatus
    availability: AssetAvailability
    last_checked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
