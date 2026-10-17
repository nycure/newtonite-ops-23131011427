import asyncio
import pytest
from httpx import AsyncClient
from app.models.work_item import WorkItem
from app.models.enums import WorkItemType, WorkItemPriority, WorkItemStatus


@pytest.mark.asyncio
async def test_concurrent_claim_race_condition(client: AsyncClient, seed_test_data, auth_headers, db_session):
    """
    Critical Behaviour 1: Concurrent Claim Collision
    When two users fire requests simultaneously to claim the exact same unassigned item:
    - Exactly one user must succeed with HTTP 200 OK.
    - The colliding user must receive HTTP 409 Conflict.
    - Database integrity must remain uncorrupted (item assigned to the winning user).
    """
    team = seed_test_data["team"]
    alice = seed_test_data["alice"]
    bob = seed_test_data["bob"]

    # 1. Create an unassigned work item
    item = WorkItem(
        title="Unassigned critical incident for concurrency test",
        description="Testing race conditions under parallel execution",
        type=WorkItemType.INCIDENT,
        priority=WorkItemPriority.URGENT,
        status=WorkItemStatus.OPEN,
        team_id=team.id,
        assignee_id=None,
        created_by_id=alice.id,
        version=1,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    item_id = item.id

    alice_headers = auth_headers(alice.id, alice.email, alice.name)
    bob_headers = auth_headers(bob.id, bob.email, bob.name)

    # 2. Fire two claim requests concurrently using asyncio.gather
    async def claim_as_alice():
        return await client.post(f"/api/items/{item_id}/claim", headers=alice_headers)

    async def claim_as_bob():
        return await client.post(f"/api/items/{item_id}/claim", headers=bob_headers)

    resp_alice, resp_bob = await asyncio.gather(claim_as_alice(), claim_as_bob())

    statuses = [resp_alice.status_code, resp_bob.status_code]

    # 3. Assertions: Exactly one 200 and one 409
    assert 200 in statuses, f"Expected one successful claim, got: {statuses}"
    assert 409 in statuses, f"Expected one 409 Conflict rejection, got: {statuses}"

    # 4. Check error detail in the 409 response
    conflict_resp = resp_alice if resp_alice.status_code == 409 else resp_bob
    success_resp = resp_alice if resp_alice.status_code == 200 else resp_bob

    assert "claimed" in conflict_resp.json()["detail"].lower()
    assert success_resp.json()["assignee_id"] in [alice.id, bob.id]

    # 5. Verify database state
    verify_resp = await client.get(f"/api/items/{item_id}", headers=alice_headers)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["assignee_id"] == success_resp.json()["assignee_id"]
    assert verify_resp.json()["version"] == 2
