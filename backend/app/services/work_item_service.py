from datetime import datetime
from typing import Optional, List, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, or_, and_, desc
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.work_item import WorkItem
from app.models.team import Team, TeamMembership
from app.models.user import User
from app.models.activity import ActivityEvent, Comment
from app.models.enums import (
    WorkItemStatus,
    WorkItemPriority,
    WorkItemType,
    ActivityEventType,
    TeamRole,
)
from app.schemas.work_item import WorkItemCreate, WorkItemUpdate
from app.services.workflow_service import validate_status_transition
from app.services.outbox_worker import create_outbox_job


def val_str(v: Any) -> str:
    """Safely extracts the string representation of an enum or string value."""
    if v is None:
        return ""
    return v.value if hasattr(v, "value") else str(v)


async def get_user_team_role(
    db: AsyncSession,
    user_id: int,
    team_id: int,
) -> Optional[TeamRole]:
    """Retrieves the user's role for a specific team, or None if not a member."""
    stmt = select(TeamMembership.role).where(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == team_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_work_items_cursor(
    db: AsyncSession,
    user_id: int,
    team_id: Optional[int] = None,
    status_filter: Optional[WorkItemStatus] = None,
    priority_filter: Optional[WorkItemPriority] = None,
    type_filter: Optional[WorkItemType] = None,
    assignee_id: Optional[int] = None,
    unassigned_only: bool = False,
    assigned_to_me: bool = False,
    awaiting_my_approval: bool = False,
    search_query: Optional[str] = None,
    cursor: Optional[int] = None,
    limit: int = 20,
) -> Tuple[List[WorkItem], int, Optional[int], bool]:
    """
    Cursor-based server-side paginated list of work items scoped to authorized teams.
    """
    user_teams_stmt = select(TeamMembership.team_id).where(TeamMembership.user_id == user_id)
    user_teams_res = await db.execute(user_teams_stmt)
    accessible_team_ids = set(user_teams_res.scalars().all())

    if not accessible_team_ids:
        return [], 0, None, False

    if team_id is not None:
        if team_id not in accessible_team_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this team's work items.",
            )
        target_team_ids = [team_id]
    else:
        target_team_ids = list(accessible_team_ids)

    filters = [WorkItem.team_id.in_(target_team_ids)]

    if status_filter:
        filters.append(WorkItem.status == val_str(status_filter))

    if priority_filter:
        filters.append(WorkItem.priority == val_str(priority_filter))

    if type_filter:
        filters.append(WorkItem.type == val_str(type_filter))

    if assigned_to_me:
        filters.append(WorkItem.assignee_id == user_id)
    elif unassigned_only:
        filters.append(WorkItem.assignee_id.is_(None))
    elif assignee_id is not None:
        filters.append(WorkItem.assignee_id == assignee_id)

    if awaiting_my_approval:
        lead_teams_stmt = select(TeamMembership.team_id).where(
            TeamMembership.user_id == user_id,
            TeamMembership.role.in_([TeamRole.LEAD.value, TeamRole.ADMIN.value, TeamRole.LEAD, TeamRole.ADMIN]),
        )
        lead_teams_res = await db.execute(lead_teams_stmt)
        lead_team_ids = lead_teams_res.scalars().all()
        filters.append(WorkItem.status == WorkItemStatus.AWAITING_APPROVAL.value)
        filters.append(WorkItem.team_id.in_(lead_team_ids))

    if search_query and search_query.strip():
        term = f"%{search_query.strip()}%"
        filters.append(or_(WorkItem.title.ilike(term), WorkItem.description.ilike(term)))

    # Count total matching
    count_stmt = select(func.count(WorkItem.id)).where(and_(*filters))
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Cursor filter (descending ID ordering)
    if cursor is not None:
        filters.append(WorkItem.id < cursor)

    # Query items with relations
    query = (
        select(WorkItem)
        .options(
            selectinload(WorkItem.team),
            selectinload(WorkItem.assignee),
            selectinload(WorkItem.creator),
        )
        .where(and_(*filters))
        .order_by(desc(WorkItem.id))
        .limit(limit + 1)
    )

    items_res = await db.execute(query)
    items = list(items_res.scalars().all())

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
        next_cursor = items[-1].id
    else:
        next_cursor = None

    return items, total_count, next_cursor, has_more


async def get_work_item_or_404(
    db: AsyncSession,
    item_id: int,
    user_id: int,
) -> WorkItem:
    """Loads a work item with detailed relations and checks team permission."""
    stmt = (
        select(WorkItem)
        .options(
            selectinload(WorkItem.team),
            selectinload(WorkItem.assignee),
            selectinload(WorkItem.creator),
            selectinload(WorkItem.activity_events).selectinload(ActivityEvent.user),
            selectinload(WorkItem.comments).selectinload(Comment.user),
        )
        .where(WorkItem.id == item_id)
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work item #{item_id} not found.",
        )

    # Authorization check
    role = await get_user_team_role(db, user_id, item.team_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view or manage items for this team.",
        )

    return item


async def create_work_item(
    db: AsyncSession,
    data: WorkItemCreate,
    creator_id: int,
    auto_commit: bool = True,
) -> WorkItem:
    """Creates a work item with audit trail and outbox event in a single atomic transaction."""
    role = await get_user_team_role(db, creator_id, data.team_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create items for a team you do not belong to.",
        )
    if val_str(role) == TeamRole.VIEWER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot create work items.",
        )

    item = WorkItem(
        title=data.title,
        description=data.description,
        type=val_str(data.type),
        priority=val_str(data.priority),
        status=WorkItemStatus.OPEN.value,
        team_id=data.team_id,
        assignee_id=data.assignee_id,
        created_by_id=creator_id,
        due_date=data.due_date,
        version=1,
    )
    db.add(item)
    await db.flush()

    # Append activity event
    event = ActivityEvent(
        work_item_id=item.id,
        user_id=creator_id,
        event_type=ActivityEventType.CREATED.value,
        to_value=val_str(item.status),
        message=f"Created work item '{item.title}' with priority '{val_str(item.priority)}'",
    )
    db.add(event)

    # Transactional outbox
    await create_outbox_job(
        db=db,
        job_type="audit_log_sync",
        payload={"work_item_id": item.id, "action": "created", "actor_id": creator_id},
    )

    if item.assignee_id:
        await create_outbox_job(
            db=db,
            job_type="notify_assignee",
            payload={"work_item_id": item.id, "assignee_id": item.assignee_id, "action": "assigned"},
        )

    if auto_commit:
        await db.commit()
    else:
        await db.flush()
    return await get_work_item_or_404(db, item.id, creator_id)


async def claim_work_item_atomic(
    db: AsyncSession,
    item_id: int,
    user_id: int,
) -> WorkItem:
    """
    Atomically claims an unassigned work item.
    Uses conditional SQL UPDATE WHERE assignee_id IS NULL to avoid race conditions.
    Returns 409 Conflict if another user claimed it first.
    """
    chk_stmt = select(WorkItem.team_id, WorkItem.assignee_id).where(WorkItem.id == item_id)
    chk_res = await db.execute(chk_stmt)
    row = chk_res.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work item #{item_id} not found.",
        )

    team_id, current_assignee_id = row
    role = await get_user_team_role(db, user_id, team_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not belong to the team that owns this work item.",
        )
    if val_str(role) == TeamRole.VIEWER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot claim work items.",
        )

    if current_assignee_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Work item #{item_id} is already claimed by another user.",
        )

    update_stmt = (
        update(WorkItem)
        .where(
            WorkItem.id == item_id,
            WorkItem.assignee_id.is_(None),
        )
        .values(
            assignee_id=user_id,
            version=WorkItem.version + 1,
            updated_at=datetime.utcnow(),
        )
    )
    result = await db.execute(update_stmt)

    if result.rowcount == 0:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrent claim collision: Work item was just claimed by another user.",
        )

    event = ActivityEvent(
        work_item_id=item_id,
        user_id=user_id,
        event_type=ActivityEventType.CLAIMED.value,
        to_value=str(user_id),
        message="Claimed work item",
    )
    db.add(event)

    await create_outbox_job(
        db=db,
        job_type="notify_assignee",
        payload={"work_item_id": item_id, "assignee_id": user_id, "action": "claimed"},
    )

    await db.commit()
    return await get_work_item_or_404(db, item_id, user_id)


async def update_work_item_optimistic(
    db: AsyncSession,
    item_id: int,
    data: WorkItemUpdate,
    user_id: int,
    auto_commit: bool = True,
) -> WorkItem:
    """
    Updates work item with optimistic locking check.
    If client version is outdated, returns 409 Conflict with latest version details.
    """
    current_item = await get_work_item_or_404(db, item_id, user_id)

    role = await get_user_team_role(db, user_id, current_item.team_id)
    if val_str(role) == TeamRole.VIEWER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot modify work items.",
        )

    if current_item.version != data.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Conflict detected: The work item was modified by another user.",
                "provided_version": data.version,
                "current_version": current_item.version,
                "latest_title": current_item.title,
                "latest_priority": val_str(current_item.priority),
                "updated_at": current_item.updated_at.isoformat() if current_item.updated_at else None,
            },
        )

    update_values = {
        "version": current_item.version + 1,
        "updated_at": datetime.utcnow(),
    }
    if data.title is not None:
        update_values["title"] = data.title
    if data.description is not None:
        update_values["description"] = data.description
    if data.priority is not None:
        update_values["priority"] = val_str(data.priority)
    if data.due_date is not None:
        update_values["due_date"] = data.due_date

    update_stmt = (
        update(WorkItem)
        .where(
            WorkItem.id == item_id,
            WorkItem.version == data.version,
        )
        .values(**update_values)
    )
    result = await db.execute(update_stmt)

    if result.rowcount == 0:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict detected: Concurrent update occurred. Please reload and retry.",
        )

    if data.priority and val_str(data.priority) != val_str(current_item.priority):
        event = ActivityEvent(
            work_item_id=item_id,
            user_id=user_id,
            event_type=ActivityEventType.PRIORITY_CHANGED.value,
            from_value=val_str(current_item.priority),
            to_value=val_str(data.priority),
            message=f"Changed priority from {val_str(current_item.priority)} to {val_str(data.priority)}",
        )
        db.add(event)
    else:
        event = ActivityEvent(
            work_item_id=item_id,
            user_id=user_id,
            event_type=ActivityEventType.UPDATED.value,
            message="Updated work item details",
        )
        db.add(event)

    await create_outbox_job(
        db=db,
        job_type="audit_log_sync",
        payload={"work_item_id": item_id, "action": "updated", "actor_id": user_id},
    )

    if auto_commit:
        await db.commit()
    else:
        await db.flush()
    return await get_work_item_or_404(db, item_id, user_id)


async def transition_work_item_workflow(
    db: AsyncSession,
    item_id: int,
    target_status: WorkItemStatus,
    user_id: int,
    comment_text: Optional[str] = None,
) -> WorkItem:
    """
    Executes a status transition validating state machine and team role permissions.
    """
    current_item = await get_work_item_or_404(db, item_id, user_id)
    role = await get_user_team_role(db, user_id, current_item.team_id)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not belong to the team for this item.",
        )

    validate_status_transition(current_item.status, target_status, role)

    old_status = current_item.status
    current_item.status = val_str(target_status)
    current_item.version += 1
    current_item.updated_at = datetime.utcnow()

    event = ActivityEvent(
        work_item_id=item_id,
        user_id=user_id,
        event_type=ActivityEventType.STATUS_CHANGED.value,
        from_value=val_str(old_status),
        to_value=val_str(target_status),
        message=f"Status changed from {val_str(old_status)} to {val_str(target_status)}",
    )
    db.add(event)

    if comment_text and comment_text.strip():
        comment = Comment(
            work_item_id=item_id,
            user_id=user_id,
            content=comment_text.strip(),
        )
        db.add(comment)

    await create_outbox_job(
        db=db,
        job_type="status_change_notification",
        payload={
            "work_item_id": item_id,
            "old_status": val_str(old_status),
            "new_status": val_str(target_status),
            "actor_id": user_id,
        },
    )

    await db.commit()
    return await get_work_item_or_404(db, item_id, user_id)


async def add_work_item_comment(
    db: AsyncSession,
    item_id: int,
    user_id: int,
    content: str,
) -> Comment:
    """Adds a comment and logs an activity event in the same transaction."""
    item = await get_work_item_or_404(db, item_id, user_id)
    role = await get_user_team_role(db, user_id, item.team_id)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot comment on items for a team you do not belong to.",
        )

    comment = Comment(
        work_item_id=item_id,
        user_id=user_id,
        content=content.strip(),
    )
    db.add(comment)

    event = ActivityEvent(
        work_item_id=item_id,
        user_id=user_id,
        event_type=ActivityEventType.COMMENT_ADDED.value,
        message=f"Added a comment: {content[:40]}...",
    )
    db.add(event)

    await db.commit()
    await db.refresh(comment)
    return comment
