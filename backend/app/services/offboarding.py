import asyncio
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Contract, Employee, EmployeeOffboarding, ProjectAssignment, SalaryRecord, User


ACTIVE_OFFBOARDING_STATUSES = {"pending", "approved", "scheduled"}
SALARY_OFFBOARDING_STATUSES = {"approved", "scheduled", "completed"}


def month_from_date(value: date) -> str:
    return value.strftime("%Y-%m")


def offboarding_final_month(row: EmployeeOffboarding) -> str:
    return row.final_salary_month or month_from_date(row.resignation_date)


def offboarding_out(row: EmployeeOffboarding) -> dict:
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "full_name": row.full_name,
        "name_kana": row.name_kana,
        "email": row.email,
        "phone": row.phone,
        "residence": row.residence,
        "nearest_station": row.nearest_station,
        "employee_type": row.employee_type,
        "resignation_date": row.resignation_date,
        "last_work_date": row.last_work_date,
        "resignation_reason": row.resignation_reason,
        "reason_detail": row.reason_detail,
        "handover_note": row.handover_note,
        "final_salary_month": offboarding_final_month(row),
        "final_salary_hours": row.final_salary_hours,
        "final_salary_amount": row.final_salary_amount,
        "final_salary_note": row.final_salary_note,
        "status": row.status,
        "requester_id": row.requester_id,
        "requester_name": row.requester.full_name if row.requester else None,
        "approver_id": row.approver_id,
        "approver_name": row.approver.full_name if row.approver else None,
        "approved_at": row.approved_at,
        "processed_at": row.processed_at,
        "attributes": row.attributes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def snapshot_from_employee(row: EmployeeOffboarding, employee: Employee) -> None:
    row.full_name = employee.full_name
    row.name_kana = employee.name_kana
    row.email = employee.email
    row.phone = employee.phone
    row.residence = employee.residence
    row.nearest_station = employee.nearest_station
    row.employee_type = employee.employee_type


def active_offboarding_for_employee(db: Session, employee_id: int) -> EmployeeOffboarding | None:
    return db.scalar(
        select(EmployeeOffboarding)
        .where(
            EmployeeOffboarding.employee_id == employee_id,
            EmployeeOffboarding.status.in_(ACTIVE_OFFBOARDING_STATUSES),
        )
        .order_by(EmployeeOffboarding.created_at.desc())
    )


def salary_offboarding_for_month(db: Session, employee_id: int, year_month: str | None) -> EmployeeOffboarding | None:
    if not year_month:
        return None
    rows = db.scalars(
        select(EmployeeOffboarding)
        .where(
            EmployeeOffboarding.employee_id == employee_id,
            EmployeeOffboarding.status.in_(SALARY_OFFBOARDING_STATUSES),
        )
        .order_by(EmployeeOffboarding.created_at.desc())
    ).all()
    for row in rows:
        if year_month >= offboarding_final_month(row):
            return row
    return None


def ensure_final_salary_record(db: Session, row: EmployeeOffboarding) -> SalaryRecord | None:
    from app.services.salary import ensure_salary_record, refresh_salary_records_for_employee

    employee = db.get(Employee, row.employee_id)
    if not employee:
        return None
    final_month = offboarding_final_month(row)
    refresh_salary_records_for_employee(
        db,
        employee.id,
        months={final_month},
        include_current=False,
        reason="offboarding_changed",
    )
    record = db.scalar(
        select(SalaryRecord).where(
            SalaryRecord.employee_id == employee.id,
            SalaryRecord.year_month == final_month,
        )
    )
    if record is None:
        record = ensure_salary_record(db, employee, final_month)
    return record


def execute_offboarding(db: Session, row: EmployeeOffboarding, approver: User | None = None) -> EmployeeOffboarding:
    if row.status == "completed":
        return row
    now = datetime.utcnow()
    row.status = "completed"
    row.processed_at = now
    if approver:
        row.approver_id = approver.id
        row.approved_at = row.approved_at or now

    attrs = dict(row.attributes or {})
    record = ensure_final_salary_record(db, row)
    if record and record.locked:
        attrs["salary_locked_warning"] = "final salary is locked; automatic offboarding recalculation was skipped"
    elif record:
        attrs["final_salary_record_id"] = record.id

    employee = db.get(Employee, row.employee_id)
    if employee:
        employee.is_deleted = True
        employee.deleted_at = now
        linked_user = db.scalar(select(User).where(User.employee_id == employee.id))
        if linked_user:
            linked_user.is_active = False
        for assignment in db.scalars(
            select(ProjectAssignment).where(
                ProjectAssignment.employee_id == employee.id,
                ProjectAssignment.status == "assigned",
            )
        ).all():
            assignment.status = "released"
        for contract in db.scalars(
            select(Contract).where(
                Contract.employee_id == employee.id,
                Contract.is_deleted.is_(False),
            )
        ).all():
            contract.is_deleted = True
            contract.deleted_at = now
            if not contract.end_date or contract.end_date > row.resignation_date:
                contract.end_date = row.resignation_date
            contract.attributes = {
                **(contract.attributes or {}),
                "offboarding_id": row.id,
                "offboarding_deleted": True,
            }

    row.attributes = attrs or None
    return row


def approve_offboarding(db: Session, row: EmployeeOffboarding, approver: User) -> EmployeeOffboarding:
    now = datetime.utcnow()
    row.approver_id = approver.id
    row.approved_at = now
    if row.resignation_date <= date.today():
        execute_offboarding(db, row, approver)
    else:
        row.status = "scheduled"
        db.flush()
        attrs = dict(row.attributes or {})
        record = ensure_final_salary_record(db, row)
        if record and record.locked:
            attrs["salary_locked_warning"] = "final salary is locked; automatic offboarding recalculation was skipped"
        elif record:
            attrs.pop("salary_locked_warning", None)
            attrs["final_salary_record_id"] = record.id
        row.attributes = attrs or None
    return row


def create_immediate_offboarding(
    db: Session,
    employee: Employee,
    requester: User,
    reason: str = "manual_delete",
) -> EmployeeOffboarding:
    today = date.today()
    row = EmployeeOffboarding(
        employee_id=employee.id,
        full_name=employee.full_name,
        name_kana=employee.name_kana,
        email=employee.email,
        phone=employee.phone,
        residence=employee.residence,
        nearest_station=employee.nearest_station,
        employee_type=employee.employee_type,
        resignation_date=today,
        last_work_date=today,
        resignation_reason=reason,
        final_salary_month=month_from_date(today),
        status="approved",
        requester_id=requester.id,
        approver_id=requester.id,
        approved_at=datetime.utcnow(),
        attributes={"source": "employee_delete"},
    )
    db.add(row)
    db.flush()
    execute_offboarding(db, row, requester)
    return row


def process_due_offboardings(db: Session) -> int:
    rows = db.scalars(
        select(EmployeeOffboarding).where(
            EmployeeOffboarding.status.in_({"approved", "scheduled"}),
            EmployeeOffboarding.resignation_date <= date.today(),
        )
    ).all()
    for row in rows:
        execute_offboarding(db, row)
    if rows:
        db.commit()
    return len(rows)


async def offboarding_loop() -> None:
    while True:
        await asyncio.sleep(3600)
        db = SessionLocal()
        try:
            process_due_offboardings(db)
        finally:
            db.close()
