from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Notification, NotificationRule, User
from app.services.mail import send_mail


def _notification_email(user: User) -> str | None:
    if user.employee and user.employee.email:
        return user.employee.email
    return user.email or None


def emit_event(
    db: Session,
    event_code: str,
    event_key: str,
    title: str,
    message: str,
    link: str | None = None,
    related_user_ids: list[int] | None = None,
    related_emails: list[str] | None = None,
    attributes: dict | None = None,
) -> int:
    rule = db.scalar(select(NotificationRule).where(NotificationRule.event_code == event_code))
    if not rule or not rule.enabled:
        return 0

    channels = set(rule.channels or [])
    if not channels:
        return 0
    user_ids = {int(value) for value in (rule.recipient_user_ids or []) if str(value).isdigit()}
    if rule.include_related:
        user_ids.update(int(value) for value in (related_user_ids or []) if value)
    recipient_roles = [str(value) for value in (rule.recipient_roles or []) if value]

    conditions = [User.id.in_(user_ids)] if user_ids else []
    if recipient_roles:
        conditions.append(User.role.in_(recipient_roles))
    users = list(db.scalars(select(User).where(User.is_active.is_(True), or_(*conditions))).unique()) if conditions else []

    digest = hashlib.sha256(f"{event_code}:{event_key}".encode("utf-8")).hexdigest()
    created = 0
    known_emails: set[str] = set()
    for user in users:
        email = _notification_email(user)
        if email:
            known_emails.add(email.lower())
        recipient_key = f"user:{user.id}"
        if db.scalar(select(Notification.id).where(Notification.event_key == digest, Notification.recipient_key == recipient_key)):
            continue
        db.add(
            Notification(
                event_key=digest,
                event_code=event_code,
                recipient_key=recipient_key,
                user_id=user.id,
                recipient_email=email,
                title=title,
                message=message,
                link=link,
                visible_in_app="in_app" in channels,
                is_read="in_app" not in channels,
                email_status="pending" if "email" in channels and email else "skipped",
                attributes=attributes,
            )
        )
        created += 1

    if "email" in channels and rule.include_related:
        for email in {str(value).strip().lower() for value in (related_emails or []) if str(value).strip()}:
            if email in known_emails:
                continue
            recipient_key = f"email:{email}"[:255]
            if db.scalar(select(Notification.id).where(Notification.event_key == digest, Notification.recipient_key == recipient_key)):
                continue
            db.add(
                Notification(
                    event_key=digest,
                    event_code=event_code,
                    recipient_key=recipient_key,
                    recipient_email=email,
                    title=title,
                    message=message,
                    link=link,
                    visible_in_app=False,
                    is_read=True,
                    email_status="pending",
                    attributes=attributes,
                )
            )
            created += 1

    db.flush()
    return created


def dispatch_pending_notifications(limit: int = 100) -> dict[str, int]:
    db = SessionLocal()
    sent = 0
    failed = 0
    try:
        rows = list(
            db.scalars(
                select(Notification)
                .where(Notification.email_status.in_(["pending", "failed"]), Notification.email_attempts < 3)
                .order_by(Notification.created_at)
                .limit(limit)
            ).all()
        )
        for row in rows:
            if not row.recipient_email:
                row.email_status = "skipped"
                continue
            row.email_attempts += 1
            try:
                if send_mail(row.recipient_email, row.title, f"{row.message}\n\n{row.link or ''}".strip()):
                    row.email_status = "sent"
                    row.emailed_at = datetime.utcnow()
                    row.email_error = None
                    sent += 1
                else:
                    row.email_status = "failed"
                    row.email_error = "SMTP is disabled or unavailable"
                    failed += 1
            except Exception as exc:
                row.email_status = "failed"
                row.email_error = str(exc)[:1000]
                failed += 1
        db.commit()
        return {"checked": len(rows), "sent": sent, "failed": failed}
    finally:
        db.close()


def notification_out(row: Notification) -> dict:
    return {
        "id": row.id,
        "event_code": row.event_code,
        "title": row.title,
        "message": row.message,
        "link": row.link,
        "is_read": row.is_read,
        "read_at": row.read_at,
        "created_at": row.created_at,
    }
