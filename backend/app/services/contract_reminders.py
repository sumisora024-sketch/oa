import asyncio
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import Contract, Employee
from app.services.mail import send_mail


LONG_TERM_END_DATE = date(9999, 12, 31)


def send_contract_due_reminders() -> int:
    settings = get_settings()
    recipient = settings.hr_reminder_email
    if not recipient:
        return 0

    today = date.today()
    soon = today + timedelta(days=30)
    db = SessionLocal()
    sent = 0
    try:
        contracts = db.scalars(
            select(Contract).where(
                Contract.end_date >= today,
                Contract.end_date <= soon,
                Contract.end_date != LONG_TERM_END_DATE,
            )
        ).all()
        for contract in contracts:
            employee = db.get(Employee, contract.employee_id)
            employee_name = employee.full_name if employee else f"employee_id={contract.employee_id}"
            send_mail(
                recipient,
                "契约到期提醒",
                f"{employee_name} 的契约 {contract.title} 将于 {contract.end_date} 到期，请确认续约或结束流程。",
            )
            sent += 1
    finally:
        db.close()
    return sent


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
            sent = await asyncio.to_thread(send_contract_due_reminders)
            print(f"[contracts] daily reminder sent: {sent}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[contracts] daily reminder failed: {exc}")
