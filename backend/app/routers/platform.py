from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import DocumentAccessPolicy, NotificationRule, User, WorkflowDefinition
from app.schemas import DocumentAccessPolicyUpdate, NotificationRuleUpdate, WorkflowDefinitionUpdate
from app.services.public_capabilities import NOTIFICATION_CHANNELS, ROLE_CODES


router = APIRouter(prefix="/platform", tags=["platform"])


def _validate_roles(roles: list[str]) -> list[str]:
    invalid = sorted(set(roles) - set(ROLE_CODES))
    if invalid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"未対応のロールです: {', '.join(invalid)}")
    return sorted(set(roles))


def _rule_out(row: NotificationRule) -> dict:
    return {
        "id": row.id,
        "event_code": row.event_code,
        "display_name": row.display_name,
        "enabled": row.enabled,
        "channels": row.channels or [],
        "recipient_roles": row.recipient_roles or [],
        "recipient_user_ids": row.recipient_user_ids or [],
        "include_related": row.include_related,
        "schedule": row.schedule or {},
        "updated_at": row.updated_at,
    }


def _workflow_out(row: WorkflowDefinition) -> dict:
    return {
        "id": row.id,
        "workflow_type": row.workflow_type,
        "display_name": row.display_name,
        "enabled": row.enabled,
        "steps": row.steps or [],
        "version": row.version,
        "updated_at": row.updated_at,
    }


def _policy_out(row: DocumentAccessPolicy) -> dict:
    return {
        "id": row.id,
        "document_type": row.document_type,
        "display_name": row.display_name,
        "allowed_roles": row.allowed_roles or [],
        "owner_access": row.owner_access,
        "related_access": row.related_access,
        "updated_at": row.updated_at,
    }


@router.get("/config")
def get_platform_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    users = list(db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name)).all())
    return {
        "roles": ROLE_CODES,
        "channels": NOTIFICATION_CHANNELS,
        "users": [{"id": row.id, "full_name": row.full_name, "email": row.email, "role": row.role} for row in users],
        "notification_rules": [_rule_out(row) for row in db.scalars(select(NotificationRule).order_by(NotificationRule.id)).all()],
        "workflow_definitions": [_workflow_out(row) for row in db.scalars(select(WorkflowDefinition).order_by(WorkflowDefinition.id)).all()],
        "document_policies": [_policy_out(row) for row in db.scalars(select(DocumentAccessPolicy).order_by(DocumentAccessPolicy.id)).all()],
    }


@router.put("/event-rules/{event_code}")
def update_event_rule(
    event_code: str,
    payload: NotificationRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    row = db.scalar(select(NotificationRule).where(NotificationRule.event_code == event_code))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知イベントが見つかりません")
    channels = sorted(set(payload.channels))
    if set(channels) - set(NOTIFICATION_CHANNELS):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未対応の通知チャネルです")
    valid_user_ids = set(db.scalars(select(User.id).where(User.id.in_(payload.recipient_user_ids))).all()) if payload.recipient_user_ids else set()
    if len(valid_user_ids) != len(set(payload.recipient_user_ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="存在しない通知先ユーザーが含まれています")
    row.enabled = payload.enabled
    row.channels = channels
    row.recipient_roles = _validate_roles(payload.recipient_roles)
    row.recipient_user_ids = sorted(valid_user_ids)
    row.include_related = payload.include_related
    row.schedule = payload.schedule
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _rule_out(row)


@router.put("/workflows/{workflow_type}")
def update_workflow_definition(
    workflow_type: str,
    payload: WorkflowDefinitionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    row = db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.workflow_type == workflow_type))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="承認フローが見つかりません")
    for step in payload.steps:
        step["roles"] = _validate_roles(step.get("roles") or [])
        ids = step.get("user_ids") or []
        valid_ids = set(db.scalars(select(User.id).where(User.id.in_(ids), User.is_active.is_(True))).all()) if ids else set()
        if len(valid_ids) != len(set(ids)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="存在しない承認担当者が含まれています")
        step["user_ids"] = sorted(valid_ids)
    row.enabled = payload.enabled
    row.steps = payload.steps
    row.version += 1
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _workflow_out(row)


@router.put("/document-policies/{document_type}")
def update_document_policy(
    document_type: str,
    payload: DocumentAccessPolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    row = db.scalar(select(DocumentAccessPolicy).where(DocumentAccessPolicy.document_type == document_type))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文書アクセス設定が見つかりません")
    row.allowed_roles = _validate_roles(payload.allowed_roles)
    row.owner_access = payload.owner_access
    row.related_access = payload.related_access
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _policy_out(row)
