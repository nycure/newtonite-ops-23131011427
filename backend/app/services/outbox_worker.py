import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.outbox import OutboxJob
from app.models.enums import OutboxJobStatus
from app.config import settings

logger = logging.getLogger("outbox_worker")


def val_str(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v)


async def create_outbox_job(
    db: AsyncSession,
    job_type: str,
    payload: Dict[str, Any],
    max_attempts: int = 3,
) -> OutboxJob:
    """Adds a transactional outbox job to the current session (committed together)."""
    job = OutboxJob(
        job_type=job_type,
        payload=json.dumps(payload, default=str),
        status=OutboxJobStatus.PENDING.value,
        attempts=0,
        max_attempts=max_attempts,
    )
    db.add(job)
    return job


async def handle_job_payload(job_type: str, payload_data: Dict[str, Any]) -> bool:
    """Idempotent job handler for different event notification types."""
    logger.info(f"[OUTBOX EXECUTOR] Processing job '{job_type}' with payload: {payload_data}")
    return True


async def _execute_outbox_batch_on_session(session: AsyncSession, batch_size: int = 20) -> int:
    now = datetime.utcnow()
    stmt = (
        select(OutboxJob)
        .where(
            OutboxJob.status.in_([OutboxJobStatus.PENDING.value, OutboxJobStatus.FAILED.value]),
            OutboxJob.attempts < OutboxJob.max_attempts,
            OutboxJob.next_run_at <= now,
        )
        .order_by(OutboxJob.created_at.asc())
        .limit(batch_size)
    )
    result = await session.execute(stmt)
    jobs = result.scalars().all()

    if not jobs:
        return 0

    for job in jobs:
        job.attempts += 1
        try:
            payload = json.loads(job.payload)
            success = await handle_job_payload(job.job_type, payload)
            if success:
                job.status = OutboxJobStatus.COMPLETED.value
                job.processed_at = datetime.utcnow()
                job.last_error = None
            else:
                raise Exception("Handler returned failure")
        except Exception as exc:
            logger.warning(f"Error executing outbox job #{job.id}: {exc}")
            job.last_error = str(exc)
            if job.attempts >= job.max_attempts:
                job.status = OutboxJobStatus.FAILED.value
            else:
                backoff_seconds = 2 ** job.attempts
                job.next_run_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
                job.status = OutboxJobStatus.FAILED.value

    await session.commit()
    return len(jobs)


async def process_outbox_batch(session: Optional[AsyncSession] = None, batch_size: int = 20) -> int:
    """Pulls and processes a batch of pending/retryable outbox jobs."""
    if session is not None:
        return await _execute_outbox_batch_on_session(session, batch_size)

    async with AsyncSessionLocal() as s:
        try:
            return await _execute_outbox_batch_on_session(s, batch_size)
        except Exception as e:
            await s.rollback()
            logger.error(f"Error in process_outbox_batch: {e}")
            return 0


async def start_outbox_worker_loop():
    """Background async worker loop running continuously while app is alive."""
    logger.info("Starting Transactional Outbox Worker background loop...")
    while True:
        try:
            processed_count = await process_outbox_batch()
            if processed_count == 0:
                await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)
            else:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Outbox worker loop received cancellation request.")
            break
        except Exception as e:
            logger.error(f"Unhandled error in outbox worker loop: {e}")
            await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)
