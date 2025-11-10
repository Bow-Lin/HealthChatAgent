from fastapi import APIRouter, Depends, Query
from typing import List
from app.db.session import get_session
from app.services.repo import Repo
from app.schemas.chat import ChatIn, ChatOut
from app.runtime.flow import make_clinical_flow

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/history", response_model=List[dict])
async def get_chat_history(
    user_id: str = Query(..., alias="user_id"),
    session=Depends(get_session),
):
    """Return chat history for a given patient."""
    repo = Repo(session)
    messages = await repo.get_messages_by_patient(user_id)
    return [
        {
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.post("", response_model=ChatOut)
async def chat_endpoint(
    payload: ChatIn,
    session=Depends(get_session),
):
    """
    Handle a chat message from frontend:
    1. Save message
    2. Run flow (triage + history + deepseek + persist)
    3. Return model reply
    """
    repo = Repo(session)
    flow = make_clinical_flow()
    shared = {
        "repo": repo,
        "tenant_id": "default",
        "encounter_id": payload.user_id,
        "input_text": payload.message,
    }

    await flow.run_async(shared)
    reply = shared.get("assistant_reply", "")
    triage = shared.get("triage_level", "normal")
    followups = shared.get("followups", "")
    warnings = shared.get("warnings", "")

    return ChatOut(reply=reply, triage_level=triage, followups=followups, warnings=warnings)
