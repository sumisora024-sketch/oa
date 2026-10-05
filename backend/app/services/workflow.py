from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import User, WorkflowDefinition, WorkflowRequest
from app.services.notifications import emit_event


def _definition(db: Session, workflow_type: str) -> WorkflowDefinition | None:
    return db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.workflow_type == workflow_type))


def _step_user_ids(db: Session, step: dict | None) -> list[int]:
    if not step:
        return []
    roles = [str(value) for value in (step.get("roles") or []) if value]
    user_ids = {int(value) for value in (step.get("user_ids") or []) if str(value).isdigit()}
    conditions = [User.id.in_(user_ids)] if user_ids else []
    if roles:
        conditions.append(User.role.in_(roles))
    if not conditions:
        return []
    return list(db.scalars(select(User.id).where(User.is_active.is_(True), or_(*conditions))).all())


def workflow_state(workflow: WorkflowRequest) -> dict | None:
    value = (workflow.attributes or {}).get("_workflow")
    return dict(value) if isinstance(value, dict) else None


def current_workflow_step(workflow: WorkflowRequest) -> dict | None:
    state = workflow_state(workflow)
    if not state:
        return None
    steps = state.get("steps") or []
    index = int(state.get("current_step") or 0)
    return steps[index] if 0 <= index < len(steps) else None


def can_process_workflow(user: User, workflow: WorkflowRequest) -> bool:
    if user.role == "admin":
        return True
    step = current_workflow_step(workflow)
    if not step:
        attrs = workflow.attributes or {}
        if workflow.approver_id == user.id or user.role in {"hr", "soumu"}:
            return True
        return user.role == "pm" and user.id in (attrs.get("related_user_ids") or [])
    if user.id in {int(value) for value in (step.get("user_ids") or []) if str(value).isdigit()}:
        return True
    return user.role in set(step.get("roles") or [])


def create_workflow_request(
    db: Session,
    workflow_type: str,
    entity_type: str,
    entity_id: int,
    title: str,
    requester_id: int | None,
    attributes: dict | None = None,
    link: str | None = None,
) -> WorkflowRequest:
    definition = _definition(db, workflow_type)
    if definition and not definition.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="この承認フローは現在停止されています")
    steps = [dict(step) for step in (definition.steps or [])] if definition else []
    attrs = dict(attributes or {})
    if steps:
        attrs["_workflow"] = {
            "definition_id": definition.id,
            "definition_version": definition.version,
            "steps": steps,
            "current_step": 0,
            "history": [],
        }
    workflow = WorkflowRequest(
        workflow_type=workflow_type,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        status="pending",
        requester_id=requester_id,
        attributes=attrs,
    )
    db.add(workflow)
    db.flush()
    step = current_workflow_step(workflow)
    approver_ids = _step_user_ids(db, step)
    admin_ids = list(db.scalars(select(User.id).where(User.role == "admin", User.is_active.is_(True))).all())
    event_code = "profile.change_submitted" if workflow_type == "employee_profile_change" else "workflow.submitted"
    emit_event(
        db,
        event_code=event_code,
        event_key=f"workflow:{workflow.id}:step:0",
        title="承認依頼があります",
        message=title,
        link=link or "/approvals/contracts",
        related_user_ids=sorted(set(approver_ids + admin_ids)),
        attributes={"workflow_id": workflow.id, "workflow_type": workflow_type, "step": 0},
    )
    return workflow


def decide_configured_workflow(
    db: Session,
    workflow: WorkflowRequest,
    user: User,
    decision: str,
    comment: str | None,
) -> bool:
    if not can_process_workflow(user, workflow):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="現在の承認ステップを処理する権限がありません")
    state = workflow_state(workflow)
    now = datetime.utcnow()
    if not state:
        workflow.status = decision
        workflow.comment = comment
        workflow.approver_id = user.id
        workflow.decided_at = now
        return True

    index = int(state.get("current_step") or 0)
    history = list(state.get("history") or [])
    history.append(
        {
            "step": index,
            "status": decision,
            "approver_id": user.id,
            "approver_name": user.full_name,
            "comment": comment,
            "decided_at": now.isoformat(),
        }
    )
    state["history"] = history
    attrs = dict(workflow.attributes or {})

    if decision == "rejected":
        workflow.status = "rejected"
        workflow.comment = comment
        workflow.approver_id = user.id
        workflow.decided_at = now
        attrs["_workflow"] = state
        workflow.attributes = attrs
        return True

    steps = state.get("steps") or []
    next_index = index + 1
    if next_index >= len(steps):
        workflow.status = "approved"
        workflow.comment = comment
        workflow.approver_id = user.id
        workflow.decided_at = now
        attrs["_workflow"] = state
        workflow.attributes = attrs
        return True

    state["current_step"] = next_index
    attrs["_workflow"] = state
    workflow.attributes = attrs
    workflow.status = "pending"
    workflow.comment = None
    workflow.approver_id = None
    workflow.decided_at = None
    approver_ids = _step_user_ids(db, steps[next_index])
    admin_ids = list(db.scalars(select(User.id).where(User.role == "admin", User.is_active.is_(True))).all())
    emit_event(
        db,
        event_code="workflow.submitted",
        event_key=f"workflow:{workflow.id}:step:{next_index}",
        title="次の承認依頼があります",
        message=workflow.title,
        link="/approvals/contracts",
        related_user_ids=sorted(set(approver_ids + admin_ids)),
        attributes={"workflow_id": workflow.id, "workflow_type": workflow.workflow_type, "step": next_index},
    )
    return False


def reset_configured_workflow(workflow: WorkflowRequest, user: User) -> None:
    state = workflow_state(workflow)
    if not state:
        workflow.status = "pending"
        workflow.comment = None
        workflow.approver_id = None
        workflow.decided_at = None
        return
    steps = state.get("steps") or []
    last_index = max(len(steps) - 1, 0)
    history = list(state.get("history") or [])
    history.append(
        {
            "step": last_index,
            "status": "withdrawn",
            "approver_id": user.id,
            "approver_name": user.full_name,
            "decided_at": datetime.utcnow().isoformat(),
        }
    )
    state["current_step"] = last_index
    state["history"] = history
    attrs = dict(workflow.attributes or {})
    attrs["_workflow"] = state
    workflow.attributes = attrs
    workflow.status = "pending"
    workflow.comment = None
    workflow.approver_id = None
    workflow.decided_at = None
