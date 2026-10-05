import logging
from collections.abc import Iterable

from sqlalchemy import event
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)
QUEUE_KEY = "salary_refresh_events"


def register_salary_refresh(
    db: Session,
    employee_id: int,
    months: Iterable[str] | None = None,
    include_current: bool = True,
    reason: str | None = None,
) -> None:
    """Queue a salary consistency refresh only after the surrounding transaction commits."""
    queue = db.info.setdefault(QUEUE_KEY, {})
    requested_months = None if months is None else set(months)
    entry = queue.get(employee_id)
    if entry is None:
        entry = {
            "months": requested_months,
            "include_current": include_current,
            "reasons": set(),
        }
        queue[employee_id] = entry
    else:
        if entry["months"] is not None:
            if requested_months is None:
                entry["months"] = None
            else:
                entry["months"].update(requested_months)
        entry["include_current"] = entry["include_current"] or include_current
    if reason:
        entry["reasons"].add(reason)


@event.listens_for(Session, "after_commit")
def dispatch_salary_refreshes(db: Session) -> None:
    queue = db.info.pop(QUEUE_KEY, {})
    if not queue:
        return
    try:
        from app.tasks import refresh_employee_salaries

        for employee_id, entry in queue.items():
            months = entry["months"]
            refresh_employee_salaries.delay(
                employee_id=employee_id,
                months=sorted(months) if months is not None else None,
                include_current=entry["include_current"],
                reasons=sorted(entry["reasons"]),
            )
    except Exception:
        # The synchronous refresh has already completed. Broker failure must not
        # turn a committed business operation into an API error.
        logger.exception("failed to enqueue salary consistency refresh")


@event.listens_for(Session, "after_rollback")
def discard_salary_refreshes(db: Session) -> None:
    db.info.pop(QUEUE_KEY, None)
