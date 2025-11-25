# app/api/chat.py
from fastapi import APIRouter, Depends, Query
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.repo import Repo
from app.schemas.chat import ChatIn, ChatOut
from app.runtime.flow import (
    make_clinical_flow,
    make_clinical_flow_qwen,
    make_clinical_flow_iflow,
)
from fastapi.responses import StreamingResponse
import json

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/history", response_model=List[dict])
async def get_chat_history(
    user_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Return chat history for a given patient."""
    repo = Repo(lambda: session)
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
    2. Run flow (triage + history + qwen + persist)
    3. Return model reply
    """
    repo = Repo(lambda: session)
    flow = make_clinical_flow_qwen()
    shared = {
        "repo": repo,
        "tenant_id": "default",
        "encounter_id": payload.user_id,  # temporary: use user_id as encounter_id
        "input_text": payload.message,
    }

    await flow.run_async(shared)

    reply = shared.get("assistant_reply", "")
    triage = shared.get("triage_level", "normal")
    followups = shared.get("followups", "")
    warnings = shared.get("warnings", "")
    print("------------------------")
    print(f"followups: {followups}")
    return ChatOut(
        reply=reply,
        triage_level=triage,
        followups=followups,
        warnings=warnings,
    )


@router.post("/stream")
async def chat_stream_endpoint(
    payload: ChatIn,
    session: AsyncSession = Depends(get_session),
):
    """
    Handle a chat message from frontend with streaming response:
    1. Save message
    2. Run flow (triage + history + iflow + reply_extract + persist) with streaming
    3. Return model reply as stream (SSE)
    """
    import asyncio

    repo = Repo(lambda: session)
    flow = make_clinical_flow_iflow()
    shared = {
        "repo": repo,
        "tenant_id": "default",
        "encounter_id": payload.user_id,  # temporary: use user_id as encounter_id
        "input_text": payload.message,
        "stream": True,  # tell IFlowChatNode to use streaming mode
    }

    async def generate_stream():
        # Initial event to indicate streaming has started
        init_payload = {
            "reply": "",
            "triage_level": None,
            "followups": "",
            "warnings": "",
            "is_streaming": True,
        }
        yield f"data: {json.dumps(init_payload, ensure_ascii=False)}\n\n"

        # Run the PocketFlow graph; this will set up assistant_reply_stream
        await flow.run_async(shared)

        # Shared context outputs
        triage_level = shared.get("triage_level", "normal")
        followups = shared.get("followups", "")
        warnings = shared.get("warnings", "")

        reply_stream = shared.get("assistant_reply_stream")

        # Case 1: streaming available
        if reply_stream is not None and hasattr(reply_stream, "__aiter__"):
            full_reply = ""
            try:
                async for chunk in reply_stream:
                    if not chunk:
                        continue
                    full_reply += chunk
                    event = {
                        "reply": full_reply,
                        "triage_level": triage_level,
                        "followups": followups,
                        "warnings": warnings,
                        "is_streaming": True,
                    }
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    # Small delay to avoid overwhelming client
                    await asyncio.sleep(0.01)
            except Exception as e:
                error_event = {
                    "reply": f"Error: {str(e)}",
                    "triage_level": triage_level,
                    "followups": followups,
                    "warnings": warnings,
                    "is_streaming": False,
                }
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            else:
                final_event = {
                    "reply": full_reply,
                    "triage_level": triage_level,
                    "followups": followups,
                    "warnings": warnings,
                    "is_streaming": False,
                }
                yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"
        else:
            # Fallback: non-streaming response
            reply_text = shared.get("assistant_reply", "")
            event = {
                "reply": reply_text,
                "triage_level": triage_level,
                "followups": followups,
                "warnings": warnings,
                "is_streaming": False,
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # Signal completion
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
