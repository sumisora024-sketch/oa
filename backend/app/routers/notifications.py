from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Notification, User
from app.services.notifications import notification_out


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Notification).where(Notification.user_id == user.id, Notification.visible_in_app.is_(True))
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    rows = db.scalars(stmt.order_by(Notification.created_at.desc()).limit(limit)).all()
    return [notification_out(row) for row in rows]


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.visible_in_app.is_(True),
            Notification.is_read.is_(False),
        )
    )
    return {"count": int(count or 0)}


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(Notification, notification_id)
    if not row or row.user_id != user.id or not row.visible_in_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知が見つかりません")
    if not row.is_read:
        row.is_read = True
        row.read_at = datetime.utcnow()
        db.commit()
    return notification_out(row)


@router.post("/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = list(
        db.scalars(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.visible_in_app.is_(True),
                Notification.is_read.is_(False),
            )
        ).all()
    )
    now = datetime.utcnow()
    for row in rows:
        row.is_read = True
        row.read_at = now
    db.commit()
    return {"ok": True, "count": len(rows)}
