import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from app.models.work_item import WorkItem


@pytest.mark.asyncio
async def test_idempotent_work_item_creation(client: AsyncClient, seed_test_data, auth_headers, db_session):
    """
    Critical Behaviour 3: Idempotent Request Handling
    When a network retry or rapid double-click submits duplicate requests with the same Idempotency-Key:
    - The first request creates the item and returns 201 Created.
    - The duplicate request returns the exact same 201 status and payload.
    - Exactly one item is created in the database (no duplicates).
    - If the same key is reused with a different payload, returns 422 Unprocessable Entity.
    """
    team = seed_test_data["team"]
    alice = seed_test_data["alice"]
    headers = auth_headers(alice.id, alice.email, alice.name)

    idempotency_key = str(uuid.uuid4())
    headers["Idempotency-Key"] = idempotency_key

    item_payload = {
        "title": "Payment Settlement Batch Replay",
        "description": "Triggered by billing worker retry policy",
        "type": "payment",
        "priority": "high",
        "team_id": team.id,
    }

    # 1. First submission
    resp1 = await client.post("/api/items", json=item_payload, headers=headers)
    assert resp1.status_code == 201
    item_id = resp1.json()["id"]
    assert resp1.json()["title"] == "Payment Settlement Batch Replay"

    # 2. Duplicate submission with identical key and payload (e.g. network retry)
    resp2 = await client.post("/api/items", json=item_payload, headers=headers)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == item_id
    assert resp2.json()["title"] == "Payment Settlement Batch Replay"

    # 3. Verify exactly ONE work item exists in DB with this title
    count_stmt = select(func.count(WorkItem.id)).where(WorkItem.title == "Payment Settlement Batch Replay")
    count_res = await db_session.execute(count_stmt)
    assert count_res.scalar() == 1, "Duplicate work items were erroneously created in the database!"

    # 4. Same key with DIFFERENT payload must be rejected with 422
    different_payload = {
        "title": "Malicious Tampered Request With Stolen Key",
        "type": "compliance",
        "priority": "low",
        "team_id": team.id,
    }
    resp3 = await client.post("/api/items", json=different_payload, headers=headers)
    assert resp3.status_code == 422
    assert "different request payload" in resp3.json()["detail"].lower()
