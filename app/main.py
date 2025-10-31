# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from app.runtime.flow import make_clinical_flow
from app.services.session import get_tenant_ctx
from app.services.repo import Repo

app = FastAPI(title="Clinical Chatbot (PocketFlow x DeepSeek)")

class ChatIn(BaseModel):
    text: str
    encounter_id: str

class ChatOut(BaseModel):
    reply: str
    triage: str | None = None
    followups: list[str] = []
    warnings: list[str] = []

@app.post("/encounters/{enc_id}/chat", response_model=ChatOut)
async def chat(enc_id: str, body: ChatIn, repo: Repo = Depends(Repo.dep), ctx=Depends(get_tenant_ctx)):
    if enc_id != body.encounter_id:
        raise HTTPException(400, "encounter_id mismatch")

    shared = {
        "tenant_id": ctx.tenant_id,
        "encounter_id": enc_id,
        "user_text": body.text,
        "repo": repo,
    }
    flow = make_clinical_flow()
    await flow.run(shared)  # PocketFlow-style async run

    return ChatOut(
        reply=shared["assistant_reply"],
        triage=shared.get("triage_level"),
        followups=shared.get("followups", []),
        warnings=shared.get("warnings", []),
    )
