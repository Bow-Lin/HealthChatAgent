from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_session
from app.services.repo import Repo
from app.schemas.patient import PatientCreate, PatientView

router = APIRouter(prefix="/api/users", tags=["users"])

TENANT_ID = "default"


@router.get("", response_model=List[PatientView])
async def list_or_search_users(
    query: Optional[str] = Query(None),
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    repo = Repo(lambda: session)
    if query:
        patients = await repo.search_patients_by_name(TENANT_ID, query, limit=limit)
    else:
        patients = await repo.list_recent_patients(TENANT_ID, limit=limit)

    return [
        PatientView(
            id=str(p.id),
            name=p.name or "Unnamed",
            last_encounter_at=p.last_encounter_at,
        )
        for p in patients
    ]


@router.post("", response_model=PatientView)
async def create_user(
    payload: PatientCreate,
    session: AsyncSession = Depends(get_session),
):
    repo = Repo(lambda: session)
    patient = await repo.create_patient(TENANT_ID, payload.name)
    return PatientView(
        id=str(patient.id),
        name=patient.name or "Unnamed",
        last_encounter_at=patient.last_encounter_at,
    )
