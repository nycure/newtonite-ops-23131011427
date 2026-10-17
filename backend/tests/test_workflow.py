import pytest
from httpx import AsyncClient
from app.models.work_item import WorkItem
from app.models.enums import WorkItemType, WorkItemPriority, WorkItemStatus


@pytest.mark.asyncio
async def test_workflow_state_machine_and_lead_approval(client: AsyncClient, seed_test_data, auth_headers, db_session):
    """
    Critical Behaviour 4: Server-Enforced Workflow & Role Gated Approval
    - Valid transitions must succeed (Open -> In Progress -> Awaiting Approval).
    - Invalid jumps (e.g. Open -> Closed directly) must be rejected with HTTP 400 Bad Request.
    - Approval step (Awaiting Approval -> Resolved) attempted by non-Lead (Bob) must be rejected with HTTP 403 Forbidden.
    - Approval step performed by team Lead (Alice) must succeed with HTTP 200 OK.
    """
    team = seed_test_data["team"]
    alice = seed_test_data["alice"]  # Lead
    bob = seed_test_data["bob"]      # Member
    alice_headers = auth_headers(alice.id, alice.email, alice.name)
    bob_headers = auth_headers(bob.id, bob.email, bob.name)

    # 1. Create an item in OPEN status
    item = WorkItem(
        title="Ledger balance discrepancy in APAC cluster",
        description="Daily reconciliation alert",
        type=WorkItemType.INCIDENT,
        priority=WorkItemPriority.HIGH,
        status=WorkItemStatus.OPEN,
        team_id=team.id,
        created_by_id=bob.id,
        version=1,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    item_id = item.id

    # 2. Test Invalid Jump: Open -> Closed directly
    bad_jump_resp = await client.post(
        f"/api/items/{item_id}/transition",
        json={"target_status": "closed"},
        headers=bob_headers,
    )
    assert bad_jump_resp.status_code == 400
    assert "invalid workflow transition" in bad_jump_resp.json()["detail"].lower()

    # 3. Test Valid Transition: Open -> In Progress
    step1_resp = await client.post(
        f"/api/items/{item_id}/transition",
        json={"target_status": "in_progress"},
        headers=bob_headers,
    )
    assert step1_resp.status_code == 200
    assert step1_resp.json()["status"] == "in_progress"

    # 4. Test Valid Transition: In Progress -> Awaiting Approval
    step2_resp = await client.post(
        f"/api/items/{item_id}/transition",
        json={"target_status": "awaiting_approval", "comment": "Fix applied to database. Requesting sign-off."},
        headers=bob_headers,
    )
    assert step2_resp.status_code == 200
    assert step2_resp.json()["status"] == "awaiting_approval"

    # 5. Non-Lead (Bob) tries to approve to Resolved -> MUST BE REJECTED 403
    unauthorized_approval_resp = await client.post(
        f"/api/items/{item_id}/transition",
        json={"target_status": "resolved"},
        headers=bob_headers,
    )
    assert unauthorized_approval_resp.status_code == 403
    assert "lead or admin" in unauthorized_approval_resp.json()["detail"].lower()

    # 6. Team Lead (Alice) approves to Resolved -> MUST SUCCEED 200
    lead_approval_resp = await client.post(
        f"/api/items/{item_id}/transition",
        json={"target_status": "resolved", "comment": "Approved following review of audit log."},
        headers=alice_headers,
    )
    assert lead_approval_resp.status_code == 200
    assert lead_approval_resp.json()["status"] == "resolved"

    # 7. Verify activity log captures the full history in order
    detail_resp = await client.get(f"/api/items/{item_id}", headers=alice_headers)
    assert detail_resp.status_code == 200
    events = detail_resp.json()["activity_events"]
    event_types = [e["event_type"] for e in events]
    assert "status_changed" in event_types
