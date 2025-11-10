# app/services/repo.py
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, AuditLog, Encounter, Patient
  # Patient/Encounter exist but not required for MVP


class Repo:
    """
    Data Access Layer (DAL) with multi-tenant guards and safe transactions.

    Usage patterns:
      - Simple read/write (auto session/commit):
          await repo.append_message(...)

      - Composed writes with atomicity:
          async with repo.transaction() as s:
              await repo.append_message(..., session=s)
              await repo.audit(..., session=s)
              # any error -> full rollback
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory

    # ---------------------------
    # Transactions
    # ---------------------------
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Yield a session with an active transaction. Rollbacks on exception."""
        async with self._session_factory() as session:
            async with session.begin():
                try:
                    yield session
                except Exception:
                    # session.begin() will rollback automatically on exception re-raise
                    raise

    # ---------------------------
    # Messages
    # ---------------------------
    async def get_messages(
        self,
        tenant_id: str,
        encounter_id: str,
        *,
        session: Optional[AsyncSession] = None,
        limit: Optional[int] = None,
    ) -> list[Message]:
        close_session = False
        if session is None:
            session = self._session_factory()
            close_session = True

        try:
            stmt = (
                select(Message)
                .where(
                    Message.tenant_id == tenant_id,
                    Message.encounter_id == encounter_id,
                )
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return list(rows)
        finally:
            if close_session:
                await session.close()

    async def append_message(
        self,
        tenant_id: str,
        encounter_id: str,
        role: str,
        content: str,
        content_json: Optional[dict[str, Any]] = None,
        *,
        session: Optional[AsyncSession] = None,
    ) -> Message:
        """Insert a new message. If no session provided, autocommits."""
        close_session = False
        created_here = False
        if session is None:
            session = self._session_factory()
            close_session = True
            created_here = True

        try:
            msg = Message(
                tenant_id=tenant_id,
                encounter_id=encounter_id,
                role=role,
                content=content,
                content_json=content_json,
            )
            session.add(msg)
            # Flush to get PKs and defaults (created_at, etc.)
            await session.flush()

            if created_here:
                await session.commit()

            # Expire to return fresh ORM object next access if needed
            await session.refresh(msg)
            return msg
        except Exception:
            if created_here:
                await session.rollback()
            raise
        finally:
            if close_session:
                await session.close()

    # ---------------------------
    # Recent encounter summaries (stub for future; not required by MVP tests)
    # ---------------------------
    async def get_recent_encounter_summaries(
        self,
        tenant_id: str,
        encounter_id: str,
        *,
        session: Optional[AsyncSession] = None,
        limit: int = 5,
    ) -> list[str]:
        """
        Return recent summaries of the same patient, excluding current encounter.
        Minimal placeholder implementation: returns empty list for MVP.
        Wire real SQL once summary lives on Encounter/Message.
        """
        return []

    # ---------------------------
    # Audits
    # ---------------------------
    async def audit(
        self,
        tenant_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        meta_json: Optional[dict[str, Any]] = None,
        *,
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Write an audit log entry. If no session provided, autocommits."""
        close_session = False
        created_here = False
        if session is None:
            session = self._session_factory()
            close_session = True
            created_here = True

        try:
            log = AuditLog(
                tenant_id=tenant_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                meta_json=meta_json,
            )
            session.add(log)
            await session.flush()
            if created_here:
                await session.commit()
        except Exception:
            if created_here:
                await session.rollback()
            raise
        finally:
            if close_session:
                await session.close()

    async def create_patient(
        self,
        tenant_id: str,
        name: str,
        *,
        session: Optional[AsyncSession] = None,
    ) -> Patient:
        """Create a new patient. If no session provided, autocommits."""
        close_session = False
        created_here = False
        if session is None:
            session = self._session_factory()
            close_session = True
            created_here = True

        try:
            patient = Patient(tenant_id=tenant_id, name=name)
            session.add(patient)
            await session.flush()
            if created_here:
                await session.commit()
            await session.refresh(patient)
            return patient
        except Exception:
            if created_here:
                await session.rollback()
            raise
        finally:
            if close_session:
                await session.close()

    async def list_recent_patients(
        self,
        tenant_id: str,
        *,
        limit: int = 20,
        session: Optional[AsyncSession] = None,
    ) -> list[Patient]:
        """Return recent patients for a tenant, ordered by creation time."""
        close_session = False
        if session is None:
            session = self._session_factory()
            close_session = True

        try:
            stmt = (
                select(Patient)
                .where(Patient.tenant_id == tenant_id)
                .order_by(Patient.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        finally:
            if close_session:
                await session.close()

    async def search_patients_by_name(
        self,
        tenant_id: str,
        name_query: str,
        *,
        limit: int = 20,
        session: Optional[AsyncSession] = None,
    ) -> list[Patient]:
        """Search patients by name (ILIKE %query%)."""
        close_session = False
        if session is None:
            session = self._session_factory()
            close_session = True

        try:
            pattern = f"%{name_query}%"
            stmt = (
                select(Patient)
                .where(
                    Patient.tenant_id == tenant_id,
                    Patient.name.ilike(pattern),
                )
                .order_by(Patient.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        finally:
            if close_session:
                await session.close()

    # ---------------------------
    # Messages by patient
    # ---------------------------
    async def get_messages_by_patient(
        self,
        tenant_id: str,
        patient_id: str,
        *,
        session: Optional[AsyncSession] = None,
    ) -> list[Message]:
        """
        Return all messages of all encounters for a given patient,
        ordered by time.
        """
        close_session = False
        if session is None:
            session = self._session_factory()
            close_session = True

        try:
            stmt = (
                select(Message)
                .join(
                    Encounter,
                    (Encounter.tenant_id == Message.tenant_id)
                    & (Encounter.id == Message.encounter_id),
                )
                .where(
                    Message.tenant_id == tenant_id,
                    Encounter.patient_id == patient_id,
                )
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        finally:
            if close_session:
                await session.close()