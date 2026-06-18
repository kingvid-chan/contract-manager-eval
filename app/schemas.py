"""Pydantic request/response schemas for the contract management system."""

import datetime
from pydantic import BaseModel, Field, field_validator
from app.models import UserRole, UserStatus, ContractStatus


# ── Auth ───────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


# ── User ───────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    email: str = Field(max_length=256)
    role: UserRole = UserRole.viewer
    status: UserStatus = UserStatus.active


class UserUpdate(BaseModel):
    password: str | None = Field(min_length=6, max_length=128, default=None)
    display_name: str | None = Field(min_length=1, max_length=128, default=None)
    email: str | None = Field(max_length=256, default=None)
    role: UserRole | None = None
    status: UserStatus | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    role: UserRole
    status: UserStatus
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Contract ───────────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    contract_no: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    party_a: str = Field(min_length=1, max_length=256)
    party_b: str = Field(min_length=1, max_length=256)
    amount: float | None = None
    sign_date: datetime.datetime | str | None = None
    start_date: datetime.datetime | str | None = None
    end_date: datetime.datetime | str | None = None
    description: str | None = None

    @field_validator("sign_date", "start_date", "end_date", mode="before")
    @classmethod
    def parse_empty_string(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class ContractUpdate(BaseModel):
    title: str | None = Field(min_length=1, max_length=256, default=None)
    party_a: str | None = Field(min_length=1, max_length=256, default=None)
    party_b: str | None = Field(min_length=1, max_length=256, default=None)
    amount: float | None = None
    sign_date: datetime.datetime | str | None = None
    start_date: datetime.datetime | str | None = None
    end_date: datetime.datetime | str | None = None
    description: str | None = None

    @field_validator("sign_date", "start_date", "end_date", mode="before")
    @classmethod
    def parse_empty_string(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class ContractResponse(BaseModel):
    id: int
    contract_no: str
    title: str
    party_a: str
    party_b: str
    amount: float | None
    status: ContractStatus
    sign_date: datetime.datetime | None
    start_date: datetime.datetime | None
    end_date: datetime.datetime | None
    description: str | None
    created_by: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ContractDetailResponse(ContractResponse):
    creator: UserResponse | None = None
    attachments: list["AttachmentResponse"] = []


class TransitionRequest(BaseModel):
    action: str = Field(description="Target status: pending, signed, terminated, draft")


# ── Attachment ─────────────────────────────────────────────────────────

class AttachmentResponse(BaseModel):
    id: int
    contract_id: int
    filename: str
    original_name: str
    file_type: str
    file_size: int
    uploaded_by: int
    uploaded_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Audit ──────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    entity_type: str
    entity_id: int | None
    detail: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
