from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import AttendanceLeaveBalance, AttendanceRequest, Employee, User, WorkCalendarDay
from app.schemas import (
    AttendanceDecisionIn,
    AttendanceLeaveBalanceIn,
    AttendanceLeaveBalanceOut,
    AttendanceRequestCreate,
    AttendanceRequestOut,
    AttendanceSettingsIn,
    AttendanceSettingsOut,
    AttendanceSummaryOut,
    WorkCalendarDayOut,
    WorkCalendarDayUpdate,
)
from app.services.attendance import (
    REQUEST_TYPES,
    attendance_request_out,
    default_daily_hours,
    generate_work_calendar_year,
    get_attendance_settings,
    leave_balance_for_employee,
    monthly_attendance_for_employee,
    month_bounds,
    request_paid_leave_days,
)
from app.services.salary import ensure_salary_records, refresh_salary_record_for_employee

router = APIRouter(prefix="/attendance", tags=["attendance"])


def current_year_month() -> str:
    return date.today().strftime("%Y-%m")


def settings_out(row) -> dict:
    return {
        "id": row.id,
        "default_start_time": row.default_start_time,
        "default_end_time": row.default_end_time,
        "break_minutes": row.break_minutes,
        "hour_step": row.hour_step,
        "default_paid_leave_days": row.default_paid_leave_days,
        "paid_leave_counts_as_work": row.paid_leave_counts_as_work,
        "leave_policies": row.leave_policies,
        "company_holidays": row.company_holidays,
        "default_daily_hours": default_daily_hours(row),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def visible_employees(db: Session, user: User) -> list[Employee]:
    if user.role in {"admin", "hr"}:
        return list(db.scalars(select(Employee).where(Employee.is_deleted.is_(False)).order_by(Employee.full_name)).all())
    if user.employee_id:
        employee = db.get(Employee, user.employee_id)
        return [employee] if employee and not employee.is_deleted else []
    return []


def sync_salary_after_attendance(db: Session, employee_id: int, work_date: date) -> None:
    record = refresh_salary_record_for_employee(db, employee_id, work_date.strftime("%Y-%m"))
    if record and record.locked:
        return


@router.get("/settings", response_model=AttendanceSettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "hr"})
    return settings_out(get_attendance_settings(db))


@router.put("/settings", response_model=AttendanceSettingsOut)
def update_settings(payload: AttendanceSettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    row = get_attendance_settings(db)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    ensure_salary_records(db, current_year_month())
    return settings_out(row)


@router.post("/calendar/import", response_model=list[WorkCalendarDayOut])
def import_calendar(year: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "hr"})
    target_year = year or date.today().year
    rows = generate_work_calendar_year(db, target_year)
    for month in range(1, 13):
        ensure_salary_records(db, f"{target_year}-{month:02d}")
    return rows


@router.get("/calendar", response_model=list[WorkCalendarDayOut])
def list_calendar(year_month: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "hr", "pm", "employee"})
    ym = year_month or current_year_month()
    start, end = month_bounds(ym)
    generate_work_calendar_year(db, start.year)
    db.commit()
    return list(
        db.scalars(
            select(WorkCalendarDay)
            .where(WorkCalendarDay.work_date >= start, WorkCalendarDay.work_date <= end)
            .order_by(WorkCalendarDay.work_date)
        ).all()
    )


@router.put("/calendar/{work_date}", response_model=WorkCalendarDayOut)
def update_calendar_day(
    work_date: date,
    payload: WorkCalendarDayUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    row = db.scalar(select(WorkCalendarDay).where(WorkCalendarDay.work_date == work_date))
    if not row:
        row = WorkCalendarDay(work_date=work_date)
        db.add(row)
    row.is_workday = payload.is_workday
    row.holiday_name = payload.holiday_name
    row.note = payload.note
    row.source = "manual"
    ensure_salary_records(db, work_date.strftime("%Y-%m"))
    db.commit()
    db.refresh(row)
    return row


@router.get("/summary", response_model=AttendanceSummaryOut)
def attendance_summary(
    year_month: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "hr", "pm", "employee"})
    ym = year_month or current_year_month()
    settings = get_attendance_settings(db)
    rows = [monthly_attendance_for_employee(db, employee, ym) for employee in visible_employees(db, user)]
    db.commit()
    return {"year_month": ym, "settings": settings_out(settings), "rows": rows}


@router.get("/requests", response_model=list[AttendanceRequestOut])
def list_requests(
    year_month: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "hr", "pm", "employee"})
    ym = year_month or current_year_month()
    start, end = month_bounds(ym)
    stmt = select(AttendanceRequest).where(AttendanceRequest.work_date >= start, AttendanceRequest.work_date <= end)
    if status_filter:
        stmt = stmt.where(AttendanceRequest.status == status_filter)
    if user.role not in {"admin", "hr"}:
        if not user.employee_id:
            return []
        stmt = stmt.where(AttendanceRequest.employee_id == user.employee_id)
    rows = db.scalars(stmt.order_by(AttendanceRequest.work_date.desc(), AttendanceRequest.created_at.desc())).all()
    return [attendance_request_out(db, row) for row in rows]


@router.post("/requests", response_model=AttendanceRequestOut)
def create_request(payload: AttendanceRequestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "hr", "pm", "employee"})
    if payload.request_type not in REQUEST_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid request_type")
    employee_id = payload.employee_id if user.role in {"admin", "hr"} else user.employee_id
    if not employee_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="employee_id is required")
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee not found")
    row = AttendanceRequest(
        employee_id=employee_id,
        work_date=payload.work_date,
        request_type=payload.request_type,
        requested_hours=payload.requested_hours,
        reason=payload.reason,
        requester_id=user.id,
        status="approved" if user.role in {"admin", "hr"} else "pending",
        approver_id=user.id if user.role in {"admin", "hr"} else None,
        approved_at=datetime.utcnow() if user.role in {"admin", "hr"} else None,
    )
    db.add(row)
    db.flush()
    if row.status == "approved":
        sync_salary_after_attendance(db, row.employee_id, row.work_date)
    db.commit()
    db.refresh(row)
    return attendance_request_out(db, row)


@router.post("/requests/{request_id}/decision", response_model=AttendanceRequestOut)
def decide_request(
    request_id: int,
    payload: AttendanceDecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "hr"})
    if payload.status not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="status must be approved/rejected/pending")
    row = db.get(AttendanceRequest, request_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attendance request not found")
    if payload.status == "approved":
        settings = get_attendance_settings(db)
        needed = request_paid_leave_days(row, settings)
        if needed:
            balance = leave_balance_for_employee(db, row.employee, row.work_date.year)
            if balance["remaining_days"] < needed:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="paid leave balance is insufficient")
        row.approver_id = user.id
        row.approved_at = datetime.utcnow()
    elif payload.status == "pending":
        row.approver_id = None
        row.approved_at = None
    else:
        row.approver_id = user.id
        row.approved_at = datetime.utcnow()
    row.status = payload.status
    sync_salary_after_attendance(db, row.employee_id, row.work_date)
    db.commit()
    db.refresh(row)
    return attendance_request_out(db, row)


@router.get("/leave-balances", response_model=list[AttendanceLeaveBalanceOut])
def list_leave_balances(
    fiscal_year: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "hr", "pm", "employee"})
    year = fiscal_year or date.today().year
    return [leave_balance_for_employee(db, employee, year) for employee in visible_employees(db, user)]


@router.put("/leave-balances", response_model=AttendanceLeaveBalanceOut)
def upsert_leave_balance(
    payload: AttendanceLeaveBalanceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "hr"})
    employee = db.get(Employee, payload.employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee not found")
    row = db.scalar(
        select(AttendanceLeaveBalance).where(
            AttendanceLeaveBalance.employee_id == payload.employee_id,
            AttendanceLeaveBalance.fiscal_year == payload.fiscal_year,
        )
    )
    if not row:
        row = AttendanceLeaveBalance(employee_id=payload.employee_id, fiscal_year=payload.fiscal_year)
        db.add(row)
    row.granted_days = payload.granted_days
    row.adjustment_days = payload.adjustment_days
    row.note = payload.note
    db.commit()
    return leave_balance_for_employee(db, employee, payload.fiscal_year)
