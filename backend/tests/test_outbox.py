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


@pytest.mark.asyncio
async def test_outbox_worker_retries_and_caps_failures(db_session):
    """
    Critical Behaviour 6b: Outbox Worker Retries & Max Attempt Limit
    - When a job handler fails, the worker increments attempts and schedules backoff.
    - When attempts reach max_attempts, the job is permanently marked FAILED and no longer polled.
    """
    from datetime import datetime, timedelta
    from unittest.mock import patch
    from app.services.outbox_worker import create_outbox_job

    # 1. Create a job configured with max_attempts=2
    job = await create_outbox_job(
        db=db_session,
        job_type="simulated_flaky_job",
        payload={"alert_id": 404},
        max_attempts=2,
    )
    await db_session.commit()
    await db_session.refresh(job)

    # 2. Simulate handler failure on attempt 1
    with patch("app.services.outbox_worker.handle_job_payload", side_effect=RuntimeError("Third-party API down")):
        processed = await process_outbox_batch(session=db_session)
        assert processed > 0
        await db_session.refresh(job)
        assert job.attempts == 1
        assert "Third-party API down" in job.last_error

        # 3. Simulate passage of time past exponential backoff
        job.next_run_at = datetime.utcnow() - timedelta(seconds=1)
        await db_session.commit()

        # 4. Attempt 2 fails and reaches max_attempts
        processed = await process_outbox_batch(session=db_session)
        assert processed > 0
        await db_session.refresh(job)
        assert job.attempts == 2
        assert job.status == OutboxJobStatus.FAILED.value

        # 5. Capped: worker will not re-process the job
        job.next_run_at = datetime.utcnow() - timedelta(seconds=1)
        await db_session.commit()
        processed = await process_outbox_batch(session=db_session)
        assert processed == 0, "Job exceeding max_attempts should not be processed again"


@pytest.mark.asyncio
async def test_outbox_handler_idempotency():
    """
    Critical Behaviour 6c: Idempotent Notification Execution
    - Processing the same job payload multiple times succeeds safely.
    """
    from app.services.outbox_worker import handle_job_payload

    payload = {"work_item_id": 42, "action": "created", "actor_id": 1}
    res1 = await handle_job_payload("audit_log_sync", payload)
    res2 = await handle_job_payload("audit_log_sync", payload)
    assert res1 is True
    assert res2 is True
