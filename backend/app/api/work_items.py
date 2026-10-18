from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.enums import WorkItemStatus, WorkItemPriority, WorkItemType
from app.schemas.work_item import (
    WorkItemCreate,
    WorkItemUpdate,
    WorkItemTransitionRequest,
    WorkItemOut,
    WorkItemDetailOut,
    WorkItemListResponse,
)
from app.schemas.activity import CommentCreate, CommentOut
from app.dependencies import get_current_user
from app.services.work_item_service import (
    list_work_items_cursor,
    get_work_item_or_404,
    create_work_item,
    claim_work_item_atomic,
    update_work_item_optimistic,
    transition_work_item_workflow,
    add_work_item_comment,
)
from app.services.idempotency_service import (
    check_idempotency_key,
    record_idempotency_key,
)

router = APIRouter(prefix="/api/items", tags=["Work Items"])


def serialize_work_item_out(item) -> dict:
    """Serializes a WorkItem model to dictionary matching WorkItemOut."""
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "type": item.type,
        "priority": item.priority,
        "status": item.status,
        "team_id": item.team_id,
        "team_name": item.team.name if item.team else None,
        "assignee_id": item.assignee_id,
        "assignee_name": item.assignee.name if item.assignee else None,
        "created_by_id": item.created_by_id,
        "creator_name": item.creator.name if item.creator else None,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "version": item.version,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def serialize_work_item_detail(item) -> dict:
    """Serializes a WorkItem model to detailed response including activity events and comments."""
    base = serialize_work_item_out(item)
    base["activity_events"] = [
        {
            "id": e.id,
            "work_item_id": e.work_item_id,
            "user_id": e.user_id,
            "user_name": e.user.name if e.user else "System",
            "event_type": e.event_type,
            "from_value": e.from_value,
            "to_value": e.to_value,
            "message": e.message,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in item.activity_events
    ]
    base["comments"] = [
        {
            "id": c.id,
            "work_item_id": c.work_item_id,
            "user_id": c.user_id,
            "user_name": c.user.name if c.user else f"User {c.user_id}",
            "content": c.content,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in item.comments
    ]
    return base


@router.get("", response_model=WorkItemListResponse)
async def get_work_items(
    team_id: Optional[int] = Query(None, description="Filter by team ID"),
    status: Optional[WorkItemStatus] = Query(None, description="Filter by status"),
    priority: Optional[WorkItemPriority] = Query(None, description="Filter by priority"),
    type: Optional[WorkItemType] = Query(None, description="Filter by item type"),
    assignee_id: Optional[int] = Query(None, description="Filter by assigned user ID"),
    unassigned_only: bool = Query(False, description="Filter unassigned items"),
    assigned_to_me: bool = Query(False, description="Filter items assigned to the current user"),
    awaiting_my_approval: bool = Query(False, description="Filter items awaiting approval on teams where user is Lead/Admin"),
    q: Optional[str] = Query(None, description="Text search on title or description"),
    cursor: Optional[int] = Query(None, description="Pagination cursor (item ID)"),
    limit: int = Query(20, ge=1, le=100, description="Page size limit"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a server-side filtered and cursor-paginated list of work items.
    Queries are automatically scoped to teams the current user belongs to.
    """
    items, total, next_cursor, has_more = await list_work_items_cursor(
        db=db,
        user_id=current_user.id,
        team_id=team_id,
        status_filter=status,
        priority_filter=priority,
        type_filter=type,
        assignee_id=assignee_id,
        unassigned_only=unassigned_only,
        assigned_to_me=assigned_to_me,
        awaiting_my_approval=awaiting_my_approval,
        search_query=q,
        cursor=cursor,
        limit=limit,
    )

    serialized_items = [serialize_work_item_out(it) for it in items]
    return WorkItemListResponse(
        items=serialized_items,
        total_count=total,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post("", response_model=WorkItemDetailOut, status_code=status.HTTP_201_CREATED)
async def create_new_work_item(
    payload: WorkItemCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new work item.
    Supports 'Idempotency-Key' header: if the exact same request is sent twice,
    the duplicate is prevented and the cached response is returned.
    """
    # 1. Idempotency check
    if idempotency_key:
        cached = await check_idempotency_key(
            db=db,
            key=idempotency_key,
            user_id=current_user.id,
            endpoint="/api/items",
            payload=payload.model_dump(),
        )
        if cached:
            status_code, body = cached
            return JSONResponse(status_code=status_code, content=body)

    # 2. Create work item inside current transaction without committing prematurely
    item = await create_work_item(db=db, data=payload, creator_id=current_user.id, auto_commit=False)
    serialized = serialize_work_item_detail(item)

    # 3. Store idempotency key if provided
    if idempotency_key:
        await record_idempotency_key(
            db=db,
            key=idempotency_key,
            user_id=current_user.id,
            endpoint="/api/items",
            payload=payload.model_dump(),
            response_code=status.HTTP_201_CREATED,
            response_body=serialized,
        )

    # 4. Commit item, activity log, outbox job, and idempotency key in a single ACID transaction
    await db.commit()

    return serialized


@router.get("/{item_id}", response_model=WorkItemDetailOut)
async def get_work_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves complete details for a work item, including full activity timeline
    and discussion comments. Enforces team-scoped authorization.
    """
    item = await get_work_item_or_404(db=db, item_id=item_id, user_id=current_user.id)
    return serialize_work_item_detail(item)


@router.patch("/{item_id}", response_model=WorkItemDetailOut)
async def update_work_item(
    item_id: int,
    payload: WorkItemUpdate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Updates work item with Optimistic Locking.
    Requires client to provide 'version'. If mismatched, returns 409 Conflict with latest state.
    """
    if idempotency_key:
        cached = await check_idempotency_key(
            db=db,
            key=idempotency_key,
            user_id=current_user.id,
            endpoint=f"/api/items/{item_id}",
            payload=payload.model_dump(),
        )
        if cached:
            status_code, body = cached
            return JSONResponse(status_code=status_code, content=body)

    item = await update_work_item_optimistic(
        db=db,
        item_id=item_id,
        data=payload,
        user_id=current_user.id,
        auto_commit=False,
    )
    serialized = serialize_work_item_detail(item)

    if idempotency_key:
        await record_idempotency_key(
            db=db,
            key=idempotency_key,
            user_id=current_user.id,
            endpoint=f"/api/items/{item_id}",
            payload=payload.model_dump(),
            response_code=status.HTTP_200_OK,
            response_body=serialized,
        )

    await db.commit()

    return serialized


@router.post("/{item_id}/claim", response_model=WorkItemDetailOut)
async def claim_work_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Atomically claims an unassigned work item.
    Protected against concurrent race conditions via conditional SQL update.
    Returns 409 Conflict if already claimed by another user.
    """
    item = await claim_work_item_atomic(db=db, item_id=item_id, user_id=current_user.id)
    return serialize_work_item_detail(item)


@router.post("/{item_id}/transition", response_model=WorkItemDetailOut)
async def transition_work_item(
    item_id: int,
    payload: WorkItemTransitionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Transitions work item status through server-enforced state machine.
    Requires Lead or Admin role on the item's team for approval to 'Resolved'.
    """
    item = await transition_work_item_workflow(
        db=db,
        item_id=item_id,
        target_status=payload.target_status,
        user_id=current_user.id,
        comment_text=payload.comment,
    )
    return serialize_work_item_detail(item)


@router.post("/{item_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def add_comment(
    item_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adds a discussion comment to the work item and records an audit event."""
    comment = await add_work_item_comment(
        db=db,
        item_id=item_id,
        user_id=current_user.id,
        content=payload.content,
    )
    return CommentOut(
        id=comment.id,
        work_item_id=comment.work_item_id,
        user_id=comment.user_id,
        user_name=current_user.name,
        content=comment.content,
        created_at=comment.created_at,
    )
