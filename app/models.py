"""SQLAlchemy ORM models for the contract management system."""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    viewer = "viewer"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class ContractStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    signed = "signed"
    terminated = "terminated"
    expired = "expired"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(128), nullable=False)
    email = Column(String(256), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.viewer)
    status = Column(SAEnum(UserStatus), nullable=False, default=UserStatus.active)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    contracts = relationship("Contract", back_populates="creator", foreign_keys="Contract.created_by")
    attachments = relationship("Attachment", back_populates="uploader", foreign_keys="Attachment.uploaded_by")
    audit_logs = relationship("AuditLog", back_populates="user")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    contract_no = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(256), nullable=False)
    party_a = Column(String(256), nullable=False)
    party_b = Column(String(256), nullable=False)
    amount = Column(Float, nullable=True)
    status = Column(SAEnum(ContractStatus), nullable=False, default=ContractStatus.draft)
    sign_date = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    creator = relationship("User", back_populates="contracts", foreign_keys=[created_by])
    attachments = relationship("Attachment", back_populates="contract", cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    original_name = Column(String(256), nullable=False)
    file_type = Column(String(16), nullable=False)  # pdf / doc / docx
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    contract = relationship("Contract", back_populates="attachments")
    uploader = relationship("User", back_populates="attachments", foreign_keys=[uploaded_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_logs")
