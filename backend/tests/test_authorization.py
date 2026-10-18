import pytest
from httpx import AsyncClient
from app.models.work_item import WorkItem
from app.models.enums import WorkItemType, WorkItemPriority, WorkItemStatus


@pytest.mark.asyncio
async def test_resource_level_authorization(client: AsyncClient, seed_test_data, auth_headers, db_session):
    """
    Critical Behaviour 5: Resource-Level Team Authorization
    - Users cannot read, create, update, or claim work items belonging to a team they do not belong to (Owen -> 403 Forbidden).
    - Viewers (Charlie) can read work items, but cannot modify, create, or claim items (403 Forbidden).
    """
    team = seed_test_data["team"]
    alice = seed_test_data["alice"]
    charlie = seed_test_data["charlie"]  # Viewer
    owen = seed_test_data["owen"]        # External Outsider (no teams)

    alice_headers = auth_headers(alice.id, alice.email, alice.name)
    charlie_headers = auth_headers(charlie.id, charlie.email, charlie.name)
    owen_headers = auth_headers(owen.id, owen.email, owen.name)

    # 1. Create a platform engineering item
    item = WorkItem(
        title="Internal Kubernetes Cluster Secrets Rotation",
        description="Confidential platform operation",
        type=WorkItemType.COMPLIANCE,
        priority=WorkItemPriority.HIGH,
        status=WorkItemStatus.OPEN,
        team_id=team.id,
        created_by_id=alice.id,
        version=1,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    item_id = item.id

    # 2. Owen (external user) attempts to read item -> 403 Forbidden
    owen_read = await client.get(f"/api/items/{item_id}", headers=owen_headers)
    assert owen_read.status_code == 403
    assert "permission" in owen_read.json()["detail"].lower()

    # 3. Owen attempts to update item -> 403 Forbidden
    owen_write = await client.patch(
        f"/api/items/{item_id}",
        json={"title": "Hacked Title", "version": 1},
        headers=owen_headers,
    )
    assert owen_write.status_code == 403

    # 4. Owen attempts to claim item -> 403 Forbidden
    owen_claim = await client.post(f"/api/items/{item_id}/claim", headers=owen_headers)
    assert owen_claim.status_code == 403

    # 5. Charlie (Viewer) CAN read the item -> 200 OK
    charlie_read = await client.get(f"/api/items/{item_id}", headers=charlie_headers)
    assert charlie_read.status_code == 200
    assert charlie_read.json()["id"] == item_id

    # 6. Charlie (Viewer) CANNOT modify or claim the item -> 403 Forbidden
    charlie_claim = await client.post(f"/api/items/{item_id}/claim", headers=charlie_headers)
    assert charlie_claim.status_code == 403
    assert "viewers cannot" in charlie_claim.json()["detail"].lower()

    # 7. Owen (Outsider) attempts to list members of unauthorized team -> 403 Forbidden
    owen_team = await client.get(f"/api/teams/{team.id}/members", headers=owen_headers)
    assert owen_team.status_code == 403
    assert "access" in owen_team.json()["detail"].lower()
