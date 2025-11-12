from pydantic import BaseModel, Field
from typing import List, Optional

class ChatIn(BaseModel):
    user_id: str
    message: str

class ChatOut(BaseModel):
    reply: str
    triage_level: Optional[str] = None
    # list of suggestions for next questions
    followups: List[str] = Field(default_factory=list)
    # safety / clinical warnings
    warnings: List[str] = Field(default_factory=list)
