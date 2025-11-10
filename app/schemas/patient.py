from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PatientCreate(BaseModel):
    name: str

class PatientView(BaseModel):
    id: str
    name: str
    last_encounter_at: Optional[datetime] = None
