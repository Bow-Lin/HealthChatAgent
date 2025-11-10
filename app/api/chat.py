from fastapi import APIRouter, Depends, Query
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.repo import Repo
from app.schemas.chat import ChatIn, ChatOut
from app.runtime.flow import make_clinical_flow

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/history", response_model=List[dict])
async def get_chat_history(
    user_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Return chat history for a given patient."""
    repo = Repo(lambda: session)  # ✅ wrap session in callable
    # 注意：get_messages_by_patient 需要 (tenant_id, patient_id)
    messages = await repo.get_messages_by_patient("default", user_id)
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
    session: AsyncSession = Depends(get_session),
):
    """
    Handle a chat message from frontend:
    1. Save message
    2. Run flow (triage + history + deepseek + persist)
    3. Return model reply
    """
    repo = Repo(lambda: session)  # ✅ wrap session in callable
    flow = make_clinical_flow()
    shared = {
        "repo": repo,
        "tenant_id": "default",
        "encounter_id": payload.user_id,  # 暂时用 user_id 当 encounter_id
        "input_text": payload.message,
    }

    # run the PocketFlow asynchronously
    await flow.run_async(shared)

    # collect outputs
    reply = shared.get("assistant_reply", "")
    triage = shared.get("triage_level", "normal")
    followups = shared.get("followups", "")
    warnings = shared.get("warnings", "")

    return ChatOut(
        reply=reply,
        triage_level=triage,
        followups=followups,
        warnings=warnings,
    )
