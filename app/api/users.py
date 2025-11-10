from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from app.db.session import get_session
from app.services.repo import Repo
from app.schemas.patient import PatientCreate, PatientView

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[PatientView])
async def list_or_search_users(
    query: Optional[str] = Query(None),
    limit: int = 20,
    session=Depends(get_session),
):
    """Search patients by name or list recent ones."""
    repo = Repo(session)
    if query:
        patients = await repo.search_patients_by_name(query, limit=limit)
    else:
        patients = await repo.list_recent_patients(limit=limit)
    return patients


@router.post("", response_model=PatientView)
async def create_user(
    payload: PatientCreate,
    session=Depends(get_session),
):
    """Create a new patient record."""
    repo = Repo(session)
    patient = await repo.create_patient(payload)
    return patient
