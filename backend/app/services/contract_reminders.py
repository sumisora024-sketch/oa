import asyncio
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import Contract, Employee, NotificationRule
from app.services.notifications import emit_event


LONG_TERM_END_DATE = date(9999, 12, 31)


def send_contract_due_reminders() -> int:
    settings = get_settings()
    today = date.today()
    db = SessionLocal()
    created = 0
    try:
        rule = db.scalar(select(NotificationRule).where(NotificationRule.event_code == "contract.expiring"))
        configured_days = (rule.schedule or {}).get("days_before", [30, 14, 7, 1]) if rule else [30, 14, 7, 1]
        days_before = {int(value) for value in configured_days if str(value).isdigit()}
        max_days = max(days_before or {30})
        contracts = db.scalars(
            select(Contract).where(
                Contract.is_deleted.is_(False),
                Contract.end_date >= today,
                Contract.end_date <= today + timedelta(days=max_days),
                Contract.end_date != LONG_TERM_END_DATE,
            )
        ).all()
        for contract in contracts:
            remaining_days = (contract.end_date - today).days
            if remaining_days not in days_before:
                continue
            employee = db.get(Employee, contract.employee_id)
            employee_name = employee.full_name if employee else f"employee_id={contract.employee_id}"
            related_user_ids = [employee.user.id] if employee and employee.user else []
            created += emit_event(
                db,
                event_code="contract.expiring",
                event_key=f"contract:{contract.id}:{contract.end_date}:{remaining_days}",
                title="契約期限のお知らせ",
                message=f"{employee_name} / {contract.title} は {contract.end_date} に終了予定です。更新または終了手続きを確認してください。",
                link="/contracts/internal",
                related_user_ids=related_user_ids,
                related_emails=[settings.hr_reminder_email] if settings.hr_reminder_email else [],
                attributes={"contract_id": contract.id, "days_before": remaining_days},
            )
        db.commit()
        return created
    finally:
        db.close()


def _seconds_until_next_nine() -> float:
    now = datetime.now()
    target = datetime.combine(now.date(), time(hour=9))
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def contract_reminder_loop() -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_nine())
        try:
            created = await asyncio.to_thread(send_contract_due_reminders)
            print(f"[contracts] daily reminders created: {created}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[contracts] daily reminder failed: {exc}")
