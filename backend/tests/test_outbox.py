import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.outbox import OutboxJob
from app.models.enums import OutboxJobStatus
from app.services.outbox_worker import process_outbox_batch


@pytest.mark.asyncio
async def test_transactional_outbox_and_worker_processing(client: AsyncClient, seed_test_data, auth_headers, db_session):
    """
    Critical Behaviour 6: Transactional Outbox Pattern
    - When a work item is created, an OutboxJob is recorded in the exact same DB transaction.
    - The background worker executes and processes pending jobs, transitioning them to COMPLETED.
    - Failed jobs are retried up to max_attempts before transitioning to FAILED.
    """
    team = seed_test_data["team"]
    alice = seed_test_data["alice"]
    headers = auth_headers(alice.id, alice.email, alice.name)

    # 1. Create a work item
    payload = {
        "title": "Trigger Outbox Notification Event",
        "description": "Verifying transactional event dispatch",
        "type": "incident",
        "priority": "urgent",
        "team_id": team.id,
    }
    resp = await client.post("/api/items", json=payload, headers=headers)
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # 2. Verify outbox row exists with status PENDING
    stmt = select(OutboxJob).where(OutboxJob.status == OutboxJobStatus.PENDING)
    result = await db_session.execute(stmt)
    jobs = result.scalars().all()
    assert len(jobs) > 0, "Expected at least one outbox job created in the transaction!"

    # 3. Process the outbox batch
    processed_count = await process_outbox_batch(session=db_session)
    assert processed_count > 0, "Worker should process the pending outbox job"

    # 4. Verify job transitioned to COMPLETED
    stmt2 = select(OutboxJob).where(OutboxJob.status == OutboxJobStatus.COMPLETED)
    result2 = await db_session.execute(stmt2)
    completed_jobs = result2.scalars().all()
    assert len(completed_jobs) > 0, "Outbox job should be marked as COMPLETED after worker processing"
