# app/db/models.py
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlalchemy import JSON
from sqlmodel import SQLModel, Field


Base = SQLModel


class EncounterStatus(str, enum.Enum):
    active = "active"
    closed = "closed"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class TimeStamped(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class PatientBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False)
    external_ref: Optional[str] = Field(default=None, index=True)


class Patient(PatientBase, TimeStamped, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class EncounterBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False)
    patient_id: int = Field(foreign_key="patient.id", index=True, nullable=False)
    status: EncounterStatus = Field(
        default=EncounterStatus.active,
        sa_column=Column(
            SAEnum(EncounterStatus, name="encounter_status"),
            nullable=False,
            default=EncounterStatus.active,
            index=True,
        ),
    )
    summary: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Encounter(EncounterBase, TimeStamped, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class MessageBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False)
    encounter_id: int = Field(foreign_key="encounter.id", index=True, nullable=False)
    role: MessageRole = Field(
        sa_column=Column(
            SAEnum(MessageRole, name="message_role"),
            nullable=False,
            default=MessageRole.user,
            index=True,
        ),
    )
    content: str = Field(nullable=False)
    content_json: Optional[dict] = Field(default=None, sa_type=JSON)


class Message(MessageBase, TimeStamped, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class AuditLogBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False)
    action: str = Field(index=True, nullable=False)
    resource_type: str = Field(index=True, nullable=False)
    resource_id: str = Field(index=True, nullable=False)
    meta_json: Optional[dict] = Field(default=None, sa_type=JSON)


class AuditLog(AuditLogBase, TimeStamped, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
