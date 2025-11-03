# tests/test_repo.py
import asyncio
import pytest
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.db.models import Base, Message, AuditLog, Patient, Encounter
from app.services.repo import Repo


@pytest.fixture(scope="session")
def anyio_backend():
    # Ensure pytest-asyncio uses asyncio backend
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    # Shared in-memory DB across connections
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


async def _bootstrap_encounter(session: AsyncSession, tenant_id: str) -> tuple[str, str]:
    """Create a patient + encounter rows and return (patient_id, encounter_id)."""
    p = Patient(tenant_id=tenant_id)
    session.add(p)
    await session.flush()
    e = Encounter(tenant_id=tenant_id, patient_id=p.id, status="active")
    session.add(e)
    await session.flush()
    return str(p.id), str(e.id)


@pytest.mark.asyncio
async def test_append_and_get_messages_ordered_and_tenant_isolated(repo: Repo, session_factory):
    tenant_a = "tA"
    tenant_b = "tB"

    # Bootstrap two encounters under different tenants
    async with session_factory() as s:
        async with s.begin():
            _, enc_a = await _bootstrap_encounter(s, tenant_a)
            _, enc_b = await _bootstrap_encounter(s, tenant_b)

    # Insert messages under different tenants
    await repo.append_message(tenant_a, enc_a, role="user", content="hello A1")
    await repo.append_message(tenant_a, enc_a, role="assistant", content="hi A2")
    await repo.append_message(tenant_b, enc_b, role="user", content="hello B1")

    # Get messages for tenant A only
    msgs_a = await repo.get_messages(tenant_a, enc_a)
    assert [m.role for m in msgs_a] == ["user", "assistant"]
    assert [m.content for m in msgs_a] == ["hello A1", "hi A2"]

    # Ensure isolation: tenant B messages are not visible via tenant A criteria
    msgs_b_wrong = await repo.get_messages(tenant_a, enc_b)
    assert msgs_b_wrong == []

    # Sanity check for tenant B with its own tenant_id
    msgs_b = await repo.get_messages(tenant_b, enc_b)
    assert len(msgs_b) == 1 and msgs_b[0].content == "hello B1"


@pytest.mark.asyncio
async def test_audit_log_written(repo: Repo, session_factory):
    tenant = "tA"
    # Prepare an encounter to produce a resource_id
    async with session_factory() as s:
        async with s.begin():
            _, enc = await _bootstrap_encounter(s, tenant)

    await repo.audit(
        tenant_id=tenant,
        action="create",
        resource_type="message",
        resource_id=enc,
        meta_json={"ok": True},
    )

    # Verify
    async with session_factory() as s:
        res = await s.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant,
                AuditLog.resource_id == enc,
                AuditLog.action == "create",
            )
        )
        logs = res.scalars().all()
        assert len(logs) == 1
        assert logs[0].meta_json.get("ok") is True


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(repo: Repo, session_factory):
    tenant = "tX"
    async with session_factory() as s:
        async with s.begin():
            _, enc = await _bootstrap_encounter(s, tenant)

    # Use one atomic transaction: write then force an error -> expect rollback
    with pytest.raises(RuntimeError):
        async with repo.transaction() as tx:
            await repo.append_message(tenant, enc, "user", "will rollback", session=tx)
            # Force error AFTER write, BEFORE commit:
            raise RuntimeError("boom")

    # Verify no message persisted
    msgs = await repo.get_messages(tenant, enc)
    assert msgs == []
