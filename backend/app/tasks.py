import asyncio
from datetime import datetime
from typing import Any, Callable

from app.celery_app import celery_app
from app.core.cache import cache
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import MonthlySettlement, SalaryRecord
from app.services.contract_reminders import send_contract_due_reminders as send_contract_due_reminders_now
from app.services.mailbox import poll_mailbox_once
from app.services.offboarding import process_due_offboardings as process_due_offboardings_now
from app.services.notifications import dispatch_pending_notifications
from app.services.salary import current_year_month, ensure_salary_records, refresh_salary_records_for_employee


def _run_with_lock(name: str, ttl_seconds: int, fn: Callable[[], Any]) -> dict[str, Any]:
    key = f"job-lock:{name}"
    if not cache.add_json_if_absent(key, {"started_at": datetime.utcnow().isoformat()}, ttl_seconds):
        return {"skipped": True, "reason": "locked", "task": name}
    started = datetime.utcnow()
    try:
        result = fn()
        return {
            "skipped": False,
            "task": name,
            "started_at": started.isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "result": result,
        }
    finally:
        cache.delete(key)


@celery_app.task(name="app.tasks.poll_mailbox")
def poll_mailbox() -> dict[str, Any]:
    return _run_with_lock(
        "poll_mailbox",
        300,
        lambda: asyncio.run(poll_mailbox_once()),
    )


@celery_app.task(name="app.tasks.send_contract_due_reminders")
def send_contract_due_reminders() -> dict[str, Any]:
    return _run_with_lock(
        "send_contract_due_reminders",
        3600,
        lambda: {"sent": send_contract_due_reminders_now()},
    )


@celery_app.task(name="app.tasks.process_due_offboardings")
def process_due_offboardings() -> dict[str, Any]:
    def run() -> dict[str, int]:
        db = SessionLocal()
        try:
            return {"processed": process_due_offboardings_now(db)}
        finally:
            db.close()

    return _run_with_lock("process_due_offboardings", 1800, run)


@celery_app.task(name="app.tasks.ensure_current_month_salary_records")
def ensure_current_month_salary_records() -> dict[str, Any]:
    def run() -> dict[str, int | str]:
        db = SessionLocal()
        try:
            month = current_year_month()
            rows = ensure_salary_records(db, month)
            return {"year_month": month, "records": len(rows)}
        finally:
            db.close()

    return _run_with_lock("ensure_current_month_salary_records", 3600, run)


@celery_app.task(
    name="app.tasks.refresh_employee_salaries",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def refresh_employee_salaries(
    self,
    employee_id: int,
    months: list[str] | None = None,
    include_current: bool = True,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        db = SessionLocal()
        try:
            result = refresh_salary_records_for_employee(
                db,
                employee_id,
                months=set(months) if months is not None else None,
                include_current=include_current,
                enqueue_after_commit=False,
            )
            settlement_updates: list[dict[str, Any]] = []
            for year_month in sorted(set(result["updated_months"] + result["locked_months"])):
                settlement = db.scalar(
                    select(MonthlySettlement).where(MonthlySettlement.year_month == year_month)
                )
                if not settlement:
                    continue
                if settlement.locked:
                    settlement_updates.append({"year_month": year_month, "locked": True})
                    continue
                salary_total = int(
                    db.scalar(
                        select(func.coalesce(func.sum(SalaryRecord.actual_salary), 0)).where(
                            SalaryRecord.year_month == year_month
                        )
                    )
                    or 0
                )
                settlement.salary_total = salary_total
                settlement.net_income = int(settlement.invoice_total or 0) - int(
                    settlement.purchase_order_total or 0
                ) - salary_total
                detail = dict(settlement.detail or {})
                detail["salary_count"] = int(
                    db.scalar(
                        select(func.count(SalaryRecord.id)).where(SalaryRecord.year_month == year_month)
                    )
                    or 0
                )
                settlement.detail = detail
                settlement_updates.append(
                    {"year_month": year_month, "locked": False, "salary_total": salary_total}
                )
            db.commit()
            result["reasons"] = reasons or []
            result["settlement_updates"] = settlement_updates
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    lock_name = f"refresh_employee_salaries:{employee_id}"
    lock_key = f"job-lock:{lock_name}"
    if not cache.add_json_if_absent(
        lock_key,
        {"started_at": datetime.utcnow().isoformat()},
        300,
    ):
        raise self.retry(countdown=2, max_retries=5)
    started = datetime.utcnow()
    try:
        result = run()
        return {
            "skipped": False,
            "task": lock_name,
            "started_at": started.isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "result": result,
        }
    finally:
        cache.delete(lock_key)


@celery_app.task(name="app.tasks.dispatch_notifications")
def dispatch_notifications() -> dict[str, Any]:
    return _run_with_lock("dispatch_notifications", 55, dispatch_pending_notifications)
