from typing import Dict, Set, Tuple, Any
from fastapi import HTTPException, status
from app.models.enums import WorkItemStatus, TeamRole

def to_val(item: Any) -> str:
    return item.value if hasattr(item, "value") else str(item)

# Define allowed status transitions: from_status_str -> set of allowed to_statuses_str
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    WorkItemStatus.OPEN.value: {WorkItemStatus.IN_PROGRESS.value},
    WorkItemStatus.IN_PROGRESS.value: {WorkItemStatus.AWAITING_APPROVAL.value, WorkItemStatus.OPEN.value},
    WorkItemStatus.AWAITING_APPROVAL.value: {WorkItemStatus.RESOLVED.value, WorkItemStatus.IN_PROGRESS.value},
    WorkItemStatus.RESOLVED.value: {WorkItemStatus.CLOSED.value, WorkItemStatus.IN_PROGRESS.value},
    WorkItemStatus.CLOSED.value: {WorkItemStatus.IN_PROGRESS.value},
}

# Transitions requiring elevated roles (Lead or Admin)
ELEVATED_TRANSITIONS: Set[Tuple[str, str]] = {
    (WorkItemStatus.AWAITING_APPROVAL.value, WorkItemStatus.RESOLVED.value),  # Approval step
    (WorkItemStatus.CLOSED.value, WorkItemStatus.IN_PROGRESS.value),         # Re-opening a closed item
}


def validate_status_transition(
    current_status: Any,
    target_status: Any,
    user_role: Any,
) -> None:
    curr_str = to_val(current_status)
    tgt_str = to_val(target_status)
    role_str = to_val(user_role)

    if curr_str == tgt_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Work item is already in '{curr_str}' status.",
        )

    allowed_targets = ALLOWED_TRANSITIONS.get(curr_str, set())
    if tgt_str not in allowed_targets:
        allowed_names = sorted(list(allowed_targets))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid workflow transition from '{curr_str}' to '{tgt_str}'. "
                f"Permitted next states: {allowed_names}"
            ),
        )

    # Check elevated transitions
    if (curr_str, tgt_str) in ELEVATED_TRANSITIONS:
        if role_str not in {TeamRole.LEAD.value, TeamRole.ADMIN.value}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Transition from '{curr_str}' to '{tgt_str}' requires a Lead or Admin role.",
            )
