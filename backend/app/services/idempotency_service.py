import hashlib
import json
from typing import Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.idempotency import IdempotencyKey


def compute_request_hash(payload: Any) -> str:
    """Computes a SHA-256 hash of the JSON-serialized request payload."""
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def check_idempotency_key(
    db: AsyncSession,
    key: str,
    user_id: int,
    endpoint: str,
    payload: Any,
) -> Optional[Tuple[int, Any]]:
    """
    Checks if an idempotency key was previously processed.
    Returns (status_code, response_body) if found and valid.
    Raises 422 if key is reused with a different payload.
    """
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.key == key,
        IdempotencyKey.user_id == user_id,
        IdempotencyKey.endpoint == endpoint,
    )
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        return None

    incoming_hash = compute_request_hash(payload)
    if entry.request_hash != incoming_hash:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency key was previously used with a different request payload.",
        )

    try:
        data = json.loads(entry.response_body)
    except Exception:
        data = entry.response_body

    return entry.response_code, data


async def record_idempotency_key(
    db: AsyncSession,
    key: str,
    user_id: int,
    endpoint: str,
    payload: Any,
    response_code: int,
    response_body: Any,
) -> IdempotencyKey:
    """Stores the execution result for an idempotency key within the current transaction."""
    request_hash = compute_request_hash(payload)
    serialized_response = json.dumps(response_body, default=str)

    idemp_entry = IdempotencyKey(
        key=key,
        user_id=user_id,
        endpoint=endpoint,
        request_hash=request_hash,
        response_code=response_code,
        response_body=serialized_response,
    )
    db.add(idemp_entry)
    return idemp_entry
