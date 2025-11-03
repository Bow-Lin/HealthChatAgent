# app/db/models.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Literal, Dict, Any

from sqlalchemy import JSON, Column, Index, text
from sqlmodel import Field, Relationship, SQLModel


# -------------------------
# Helpers
# -------------------------

def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


# -------------------------
# Base mixins
# -------------------------

class TimeStamped(SQLModel):
    """Common timestamps for auditing."""
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


# -------------------------
# Core entities
# -------------------------

class PatientBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False, description="Multi-tenant isolation key")
    external_ref: Optional[str] = Field(
        default=None, index=True, description="External system reference (e.g., HIS/EMR ID)"
    )
    # Keep free-form profile as JSON (non-PII ideally). Encrypt PII at service layer if stored.
    profile_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Arbitrary patient profile blob (minimized).",
    )


class Patient(PatientBase, TimeStamped, table=True):
    """Patient record (minimal)."""
    __tablename__ = "patient"

    id: str = Field(primary_key=True, description="UUID or ULID")

    # Relationships
    encounters: List["Encounter"] = Relationship(back_populates="patient")


class EncounterBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False)
    patient_id: str = Field(foreign_key="patient.id", index=True, nullable=False)
    status: Literal["open", "closed"] = Field(default="open", index=True)
    started_at: datetime = Field(default_factory=utcnow, nullable=False)
    closed_at: Optional[datetime] = Field(default=None, nullable=True)
    summary: Optional[str] = Field(
        default=None, description="Short rolling summary for retrieval / display."
    )


class Encounter(EncounterBase, TimeStamped, table=True):
    """One clinical chat episode; all turns (messages) belong to an encounter."""
    __tablename__ = "encounter"

    id: str = Field(primary_key=True, description="UUID/ULID/KSUID")

    # Relationships
    patient: Patient = Relationship(back_populates="encounters")
    messages: List["Message"] = Relationship(back_populates="encounter")


class MessageBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False)
    encounter_id: str = Field(foreign_key="encounter.id", index=True, nullable=False)

    # OpenAI-compatible roles
    role: Literal["system", "user", "assistant", "tool"] = Field(index=True)

    # Plaintext content for search; large payloads should go to content_json.
    content_text: str = Field(description="Primary textual content of the message.")

    # Optional structured content (chunks, tool outputs, safety notes, etc.)
    content_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Optional structured content for the message.",
    )

    # Timestamp to order turns within encounter
    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)


class Message(MessageBase, table=True):
    """Conversation turn bound to an encounter."""
    __tablename__ = "message"

    id: str = Field(primary_key=True, description="UUID/ULID")

    # Relationships
    encounter: Encounter = Relationship(back_populates="messages")


class AuditLogBase(SQLModel):
    tenant_id: str = Field(index=True, nullable=False)
    action: str = Field(index=True, description="Action keyword (e.g., chat.turn, encounter.create)")
    resource_type: str = Field(index=True, description="patient|encounter|message|…")
    resource_id: str = Field(index=True, description="ID of the target resource")
    meta_json: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True), description="Additional audit context"
    )
    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)


class AuditLog(AuditLogBase, table=True):
    """Immutable audit trail for compliance & debugging."""
    __tablename__ = "audit_log"

    id: str = Field(primary_key=True, description="UUID/ULID")


# -------------------------
# Table indexes
# -------------------------

# Composite indexes that are commonly queried by the service layer
Index(
    "ix_message_tenant_enc_created",
    Message.__table__.c.tenant_id,
    Message.__table__.c.encounter_id,
    Message.__table__.c.created_at,
)
Index(
    "ix_encounter_tenant_patient_started",
    Encounter.__table__.c.tenant_id,
    Encounter.__table__.c.patient_id,
    Encounter.__table__.c.started_at,
)
Index(
    "ix_audit_tenant_resource_time",
    AuditLog.__table__.c.tenant_id,
    AuditLog.__table__.c.resource_type,
    AuditLog.__table__.c.resource_id,
    AuditLog.__table__.c.created_at,
)
