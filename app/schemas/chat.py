from pydantic import BaseModel
from typing import Optional

class ChatIn(BaseModel):
    user_id: str
    message: str

class ChatOut(BaseModel):
    reply: str
    triage_level: Optional[str] = None
    followups: Optional[str] = None
    warnings: Optional[str] = None
