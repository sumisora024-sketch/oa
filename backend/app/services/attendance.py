from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AttendanceLeaveBalance, AttendanceRequest, AttendanceSetting, Employee, SalaryRecord, WorkCalendarDay


REQUEST_TYPES = {
    "paid_leave",
    "absence",
    "morning_off",
    "afternoon_off",
    "special_leave",
    "holiday_work",
    "adjustment",
}


def time_to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def round_to_step(value: float, step: float = 0.5) -> float:
    if step <= 0:
        return round(value, 1)
    return round(round(value / step) * step, 2)


def default_daily_hours(settings: AttendanceSetting) -> float:
    minutes = time_to_minutes(settings.default_end_time) - time_to_minutes(settings.default_start_time) - settings.break_minutes
    return max(round_to_step(minutes / 60, settings.hour_step), 0)


def default_leave_policies(settings: AttendanceSetting) -> dict:
    daily = default_daily_hours(settings)
    half = round_to_step(daily / 2, settings.hour_step)
    policies = {
        "paid_leave": {
            "label": "Paid leave",
            "counts_as_work": bool(settings.paid_leave_counts_as_work),
            "consumes_paid_leave": True,
            "used_days": 1.0,
            "work_hours": daily if settings.paid_leave_counts_as_work else 0,
        },
        "absence": {
            "label": "Absence",
            "counts_as_work": False,
            "consumes_paid_leave": False,
            "used_days": 0,
            "work_hours": 0,
        },
        "morning_off": {
            "label": "Morning off",
            "counts_as_work": False,
            "consumes_paid_leave": True,
            "used_days": 0.5,
            "work_hours": half,
        },
        "afternoon_off": {
            "label": "Afternoon off",
            "counts_as_work": False,
            "consumes_paid_leave": True,
            "used_days": 0.5,
            "work_hours": half,
        },
        "special_leave": {
            "label": "Special leave",
            "counts_as_work": True,
            "consumes_paid_leave": False,
            "used_days": 0,
            "work_hours": daily,
        },
        "holiday_work": {
            "label": "Holiday work",
            "counts_as_work": True,
            "consumes_paid_leave": False,
            "used_days": 0,
            "work_hours": daily,
        },
        "adjustment": {
            "label": "Manual adjustment",
            "counts_as_work": True,
            "consumes_paid_leave": False,
            "used_days": 0,
            "work_hours": daily,
        },
    }
    for key, value in (settings.leave_policies or {}).items():
        if key in policies and isinstance(value, dict):
            policies[key].update(value)
    return policies


def get_attendance_settings(db: Session) -> AttendanceSetting:
    row = db.get(AttendanceSetting, 1)
    if not row:
        row = AttendanceSetting(id=1)
        db.add(row)
        db.flush()
    return row


def nth_monday(year: int, month: int, nth: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != 0:
        current += timedelta(days=1)
    return current + timedelta(days=(nth - 1) * 7)


def vernal_equinox_day(year: int) -> int:
    return int(20.8431 + 0.242194 * (year - 1980) - int((year - 1980) / 4))


def autumnal_equinox_day(year: int) -> int:
    return int(23.2488 + 0.242194 * (year - 1980) - int((year - 1980) / 4))


def japanese_public_holidays(year: int) -> dict[date, str]:
    holidays = {
        date(year, 1, 1): "New Year's Day",
        nth_monday(year, 1, 2): "Coming of Age Day",
        date(year, 2, 11): "National Foundation Day",
        date(year, 2, 23): "Emperor's Birthday",
        date(year, 3, vernal_equinox_day(year)): "Vernal Equinox Day",
        date(year, 4, 29): "Showa Day",
        date(year, 5, 3): "Constitution Memorial Day",
        date(year, 5, 4): "Greenery Day",
        date(year, 5, 5): "Children's Day",
        nth_monday(year, 7, 3): "Marine Day",
        date(year, 8, 11): "Mountain Day",
        nth_monday(year, 9, 3): "Respect for the Aged Day",
        date(year, 9, autumnal_equinox_day(year)): "Autumnal Equinox Day",
        nth_monday(year, 10, 2): "Sports Day",
        date(year, 11, 3): "Culture Day",
        date(year, 11, 23): "Labor Thanksgiving Day",
    }
    for holiday, name in list(holidays.items()):
        if holiday.weekday() == 6:
            substitute = holiday + timedelta(days=1)
            while substitute in holidays:
                substitute += timedelta(days=1)
            holidays[substitute] = f"Substitute Holiday ({name})"
    current = date(year, 1, 2)
    end = date(year, 12, 30)
    while current <= end:
        if current not in holidays and (current - timedelta(days=1)) in holidays and (current + timedelta(days=1)) in holidays:
            holidays[current] = "Citizen's Holiday"
        current += timedelta(days=1)
    return holidays


def company_holiday_map(settings: AttendanceSetting, year: int) -> dict[date, str]:
    result: dict[date, str] = {}
    for item in settings.company_holidays or []:
        if not isinstance(item, dict) or not item.get("date"):
            continue
        try:
            day = date.fromisoformat(str(item["date"]))
        except ValueError:
            continue
        if day.year == year:
            result[day] = str(item.get("name") or "Company Holiday")
    return result


def generate_work_calendar_year(db: Session, year: int, overwrite_manual: bool = False) -> list[WorkCalendarDay]:
    settings = get_attendance_settings(db)
    public = japanese_public_holidays(year)
    company = company_holiday_map(settings, year)
    rows: list[WorkCalendarDay] = []
    current = date(year, 1, 1)
    end = date(year, 12, 31)
    while current <= end:
        name = public.get(current) or company.get(current)
        is_workday = current.weekday() < 5 and not name
        source = "company" if current in company else "system"
        row = db.scalar(select(WorkCalendarDay).where(WorkCalendarDay.work_date == current))
        if not row:
            row = WorkCalendarDay(work_date=current)
            db.add(row)
        if overwrite_manual or row.source != "manual":
            row.is_workday = is_workday
            row.holiday_name = name
            row.source = source
        rows.append(row)
        current += timedelta(days=1)
    db.flush()
    return rows


def month_bounds(year_month: str) -> tuple[date, date]:
    year, month = [int(part) for part in year_month.split("-", 1)]
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def ensure_calendar_for_month(db: Session, year_month: str) -> None:
    start, end = month_bounds(year_month)
    count = len(
        db.scalars(
            select(WorkCalendarDay.id).where(WorkCalendarDay.work_date >= start, WorkCalendarDay.work_date <= end)
        ).all()
    )
    if count < end.day:
        generate_work_calendar_year(db, start.year)


def calendar_days_for_month(db: Session, year_month: str) -> list[WorkCalendarDay]:
    ensure_calendar_for_month(db, year_month)
    start, end = month_bounds(year_month)
    return list(
        db.scalars(
            select(WorkCalendarDay)
            .where(WorkCalendarDay.work_date >= start, WorkCalendarDay.work_date <= end)
            .order_by(WorkCalendarDay.work_date)
        ).all()
    )


def approved_requests_for_employee_month(db: Session, employee_id: int, year_month: str) -> list[AttendanceRequest]:
    start, end = month_bounds(year_month)
    return list(
        db.scalars(
            select(AttendanceRequest)
            .where(
                AttendanceRequest.employee_id == employee_id,
                AttendanceRequest.work_date >= start,
                AttendanceRequest.work_date <= end,
                AttendanceRequest.status == "approved",
            )
            .order_by(AttendanceRequest.work_date, AttendanceRequest.created_at.desc())
        ).all()
    )


def request_paid_leave_days(row: AttendanceRequest, settings: AttendanceSetting) -> float:
    policies = default_leave_policies(settings)
    policy = policies.get(row.request_type) or {}
    return float(policy.get("used_days") or 0) if policy.get("consumes_paid_leave") else 0.0


def request_work_hours(row: AttendanceRequest, base_hours: float, settings: AttendanceSetting) -> float:
    policies = default_leave_policies(settings)
    policy = policies.get(row.request_type) or {}
    if row.request_type in {"holiday_work", "adjustment"} and row.requested_hours is not None:
        return round_to_step(float(row.requested_hours), settings.hour_step)
    if row.request_type in {"morning_off", "afternoon_off"}:
        return round_to_step(base_hours / 2, settings.hour_step)
    value = policy.get("work_hours")
    if value is None:
        value = base_hours
    return round_to_step(float(value), settings.hour_step)


def used_paid_leave_days(db: Session, employee_id: int, fiscal_year: int) -> float:
    settings = get_attendance_settings(db)
    start = date(fiscal_year, 1, 1)
    end = date(fiscal_year, 12, 31)
    rows = db.scalars(
        select(AttendanceRequest).where(
            AttendanceRequest.employee_id == employee_id,
            AttendanceRequest.work_date >= start,
            AttendanceRequest.work_date <= end,
            AttendanceRequest.status == "approved",
        )
    ).all()
    return sum(request_paid_leave_days(row, settings) for row in rows)


def leave_balance_for_employee(db: Session, employee: Employee, fiscal_year: int) -> dict:
    settings = get_attendance_settings(db)
    balance = db.scalar(
        select(AttendanceLeaveBalance).where(
            AttendanceLeaveBalance.employee_id == employee.id,
            AttendanceLeaveBalance.fiscal_year == fiscal_year,
        )
    )
    granted = balance.granted_days if balance else settings.default_paid_leave_days
    adjustment = balance.adjustment_days if balance else 0.0
    used = used_paid_leave_days(db, employee.id, fiscal_year)
    return {
        "id": balance.id if balance else None,
        "employee_id": employee.id,
        "employee_name": employee.full_name,
        "fiscal_year": fiscal_year,
        "granted_days": float(granted),
        "adjustment_days": float(adjustment),
        "used_days": float(used),
        "remaining_days": float(granted + adjustment - used),
        "note": balance.note if balance else None,
    }


def monthly_attendance_for_employee(db: Session, employee: Employee, year_month: str) -> dict:
    settings = get_attendance_settings(db)
    days = calendar_days_for_month(db, year_month)
    requests = approved_requests_for_employee_month(db, employee.id, year_month)
    request_by_day: dict[date, AttendanceRequest] = {}
    for row in requests:
        request_by_day.setdefault(row.work_date, row)
    daily_hours = default_daily_hours(settings)
    scheduled_workdays = 0
    scheduled_hours = 0.0
    actual_hours = 0.0
    paid_leave_days = 0.0
    for day in days:
        base = daily_hours if day.is_workday else 0.0
        if day.is_workday:
            scheduled_workdays += 1
            scheduled_hours += daily_hours
        request = request_by_day.get(day.work_date)
        if request:
            actual_hours += request_work_hours(request, base, settings)
            paid_leave_days += request_paid_leave_days(request, settings)
        else:
            actual_hours += base
    start, end = month_bounds(year_month)
    pending = len(
        db.scalars(
            select(AttendanceRequest.id).where(
                AttendanceRequest.employee_id == employee.id,
                AttendanceRequest.work_date >= start,
                AttendanceRequest.work_date <= end,
                AttendanceRequest.status == "pending",
            )
        ).all()
    )
    salary = db.scalar(
        select(SalaryRecord).where(SalaryRecord.employee_id == employee.id, SalaryRecord.year_month == year_month)
    )
    balance = leave_balance_for_employee(db, employee, start.year)
    return {
        "employee_id": employee.id,
        "employee_name": employee.full_name,
        "year_month": year_month,
        "scheduled_workdays": scheduled_workdays,
        "scheduled_hours": round_to_step(scheduled_hours, settings.hour_step),
        "actual_work_hours": round_to_step(actual_hours, settings.hour_step),
        "paid_leave_used_days": paid_leave_days,
        "paid_leave_remaining_days": balance["remaining_days"],
        "pending_requests": pending,
        "salary_locked": bool(salary.locked) if salary else False,
    }


def monthly_work_hours(db: Session, employee_id: int, year_month: str) -> float | None:
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        return None
    return monthly_attendance_for_employee(db, employee, year_month)["actual_work_hours"]


def attendance_request_out(db: Session, row: AttendanceRequest) -> dict:
    settings = get_attendance_settings(db)
    salary = db.scalar(
        select(SalaryRecord).where(SalaryRecord.employee_id == row.employee_id, SalaryRecord.year_month == row.work_date.strftime("%Y-%m"))
    )
    calendar_row = db.scalar(select(WorkCalendarDay).where(WorkCalendarDay.work_date == row.work_date))
    base = default_daily_hours(settings) if calendar_row and calendar_row.is_workday else 0.0
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": row.employee.full_name if row.employee else None,
        "work_date": row.work_date,
        "year_month": row.work_date.strftime("%Y-%m"),
        "request_type": row.request_type,
        "requested_hours": row.requested_hours,
        "calculated_hours": request_work_hours(row, base, settings) if row.status == "approved" else None,
        "status": row.status,
        "reason": row.reason,
        "requester_name": row.requester.full_name if row.requester else None,
        "approver_name": row.approver.full_name if row.approver else None,
        "approved_at": row.approved_at,
        "salary_locked": bool(salary.locked) if salary else False,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
