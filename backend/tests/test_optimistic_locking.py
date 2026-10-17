import pytest
from httpx import AsyncClient
from app.models.work_item import WorkItem
from app.models.enums import WorkItemType, WorkItemPriority, WorkItemStatus


@pytest.mark.asyncio
async def test_optimistic_locking_stale_update_rejected(client: AsyncClient, seed_test_data, auth_headers, db_session):
    """
    Critical Behaviour 2: Optimistic Locking / Stale Edit Protection
    When a client tries to update an item using an outdated version number:
    - The server must reject the edit with HTTP 409 Conflict.
    - The server must return the latest version info to allow client reconciliation.
    - Database state must remain unmodified by the stale request.
    """
    team = seed_test_data["team"]
    alice = seed_test_data["alice"]
    bob = seed_test_data["bob"]

    # 1. Create work item at version 1
    item = WorkItem(
        title="Original Title Version 1",
        description="Original Description",
        type=WorkItemType.TASK,
        priority=WorkItemPriority.LOW,
        status=WorkItemStatus.OPEN,
        team_id=team.id,
        created_by_id=alice.id,
        version=1,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    item_id = item.id

    alice_headers = auth_headers(alice.id, alice.email, alice.name)
    bob_headers = auth_headers(bob.id, bob.email, bob.name)

    # 2. Alice updates item successfully with version 1
    alice_payload = {
        "title": "Alice's Valid Update",
        "priority": "high",
        "version": 1,
    }
    resp1 = await client.patch(f"/api/items/{item_id}", json=alice_payload, headers=alice_headers)
    assert resp1.status_code == 200
    assert resp1.json()["version"] == 2
    assert resp1.json()["title"] == "Alice's Valid Update"

    # 3. Bob attempts to submit an edit using the STALE version 1 (which he loaded earlier)
    bob_stale_payload = {
        "title": "Bob's Stale Update That Must Fail",
        "priority": "urgent",
        "version": 1,  # Stale! DB is now at version 2
    }
    resp2 = await client.patch(f"/api/items/{item_id}", json=bob_stale_payload, headers=bob_headers)

    # 4. Assert 409 Conflict rejection
    assert resp2.status_code == 409
    error_data = resp2.json()["detail"]
    assert "conflict" in error_data["message"].lower()
    assert error_data["provided_version"] == 1
    assert error_data["current_version"] == 2

    # 5. Verify database was NOT changed by Bob's stale edit
    verify_resp = await client.get(f"/api/items/{item_id}", headers=alice_headers)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["title"] == "Alice's Valid Update"
    assert verify_resp.json()["priority"] == "high"
    assert verify_resp.json()["version"] == 2
