from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.core.ui_permissions import UI_ROLES, UI_ROUTE_KEYS, normalize_route_keys, ui_permissions_for_all_roles
from app.db import get_db
from app.deps import get_current_user
from app.models import UiRolePermission, User
from app.schemas import UiPermissionOut, UiPermissionUpdate

router = APIRouter(prefix="/ui-permissions", tags=["ui_permissions"])


@router.get("", response_model=UiPermissionOut)
def list_ui_permissions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    return {
        "roles": UI_ROLES,
        "items": UI_ROUTE_KEYS,
        "permissions": ui_permissions_for_all_roles(db),
        "locked_roles": ["admin"],
    }


@router.put("/{role}", response_model=UiPermissionOut)
def update_ui_permissions(
    role: str,
    payload: UiPermissionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    if role not in UI_ROLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="role not found")
    if role == "admin":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="admin menu permission is locked")

    row = db.scalar(select(UiRolePermission).where(UiRolePermission.role == role))
    if not row:
        row = UiRolePermission(role=role, route_keys=[], updated_by=user.id)
        db.add(row)
    row.route_keys = normalize_route_keys(payload.route_keys)
    row.updated_by = user.id
    db.commit()
    return {
        "roles": UI_ROLES,
        "items": UI_ROUTE_KEYS,
        "permissions": ui_permissions_for_all_roles(db),
        "locked_roles": ["admin"],
    }
