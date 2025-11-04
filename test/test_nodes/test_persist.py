# tests/test_nodes/test_persist.py
import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.db.models import Base, Patient, Encounter, Message, AuditLog
from app.services.repo import Repo
from app.runtime.nodes.persist import PersistNode


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture()
def repo(session_factory):
    return Repo(session_factory)


async def _bootstrap_encounter(session: AsyncSession, tenant_id: str) -> str:
    p = Patient(tenant_id=tenant_id)
    session.add(p)
    await session.flush()
    e = Encounter(tenant_id=tenant_id, patient_id=p.id, status="active")
    session.add(e)
    await session.flush()
    return str(e.id)


@pytest.mark.asyncio
async def test_persist_writes_user_then_assistant_and_audit(repo: Repo, session_factory):
    tenant = "t1"
    async with session_factory() as s:
        async with s.begin():
            enc_id = await _bootstrap_encounter(s, tenant)

    node = PersistNode()
    shared = {
        "repo": repo,
        "tenant_id": tenant,
        "encounter_id": enc_id,
        "user_text": "u1",
        "to_persist": [
            {"role": "assistant", "content": "a1"},
            {"role": "assistant", "content": "a2"},
        ],
    }
    await node.exec(shared)

    async with session_factory() as s:
        res = await s.execute(
            select(Message).where(
                Message.tenant_id == tenant,
                Message.encounter_id == int(enc_id),
            ).order_by(Message.created_at.asc(), Message.id.asc())
        )
        msgs = res.scalars().all()
        assert [m.role for m in msgs] == ["user", "assistant", "assistant"]
        assert [m.content for m in msgs] == ["u1", "a1", "a2"]

        res2 = await s.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant,
                AuditLog.resource_id == enc_id,
                AuditLog.action == "chat.append",
            )
        )
        logs = res2.scalars().all()
        assert len(logs) == 1
        assert logs[0].meta_json.get("count") == 3


class ProxyRepo(Repo):
    def __init__(self, session_factory, boom_on_content: str):
        super().__init__(session_factory)
        self._boom = boom_on_content

    async def append_message(self, tenant_id, encounter_id, role, content, content_json=None, *, session=None):
        if content == self._boom:
            raise RuntimeError("boom")
        return await super().append_message(tenant_id, encounter_id, role, content, content_json, session=session)


@pytest.mark.asyncio
async def test_persist_rolls_back_on_error(session_factory):
    tenant = "t2"
    async with session_factory() as s:
        async with s.begin():
            enc_id = await _bootstrap_encounter(s, tenant)

    repo = ProxyRepo(session_factory, boom_on_content="fail-here")
    node = PersistNode()
    shared = {
        "repo": repo,
        "tenant_id": tenant,
        "encounter_id": enc_id,
        "user_text": "ok-user",
        "to_persist": [
            {"role": "assistant", "content": "fail-here"},
        ],
    }

    with pytest.raises(RuntimeError):
        await node.exec(shared)

    async with session_factory() as s:
        res = await s.execute(
            select(Message).where(
                Message.tenant_id == tenant,
                Message.encounter_id == int(enc_id),
            )
        )
        msgs = res.scalars().all()
        assert msgs == []

        res2 = await s.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant,
                AuditLog.resource_id == enc_id,
                AuditLog.action == "chat.append",
            )
        )
        assert res2.scalars().first() is None
