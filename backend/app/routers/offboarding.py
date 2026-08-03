from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import Employee, EmployeeOffboarding, User, WorkflowRequest
from app.schemas import EmployeeOffboardingCreate, EmployeeOffboardingOut, EmployeeOffboardingUpdate
from app.services.offboarding import active_offboarding_for_employee, month_from_date, offboarding_out, snapshot_from_employee

router = APIRouter(prefix="/offboardings", tags=["offboardings"])


def can_access_offboarding(user: User, row: EmployeeOffboarding) -> bool:
    return user.role in {"admin", "hr"} or user.employee_id == row.employee_id


def target_employee(db: Session, payload: EmployeeOffboardingCreate, user: User) -> Employee:
    employee_id = payload.employee_id if user.role in {"admin", "hr"} else user.employee_id
    if not employee_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="employee_id is required")
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee not found")
    return employee


@router.get("", response_model=list[EmployeeOffboardingOut])
def list_offboardings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role in {"admin", "hr"}:
        rows = db.scalars(select(EmployeeOffboarding).order_by(EmployeeOffboarding.created_at.desc())).all()
    elif user.employee_id:
        rows = db.scalars(
            select(EmployeeOffboarding)
            .where(EmployeeOffboarding.employee_id == user.employee_id)
            .order_by(EmployeeOffboarding.created_at.desc())
        ).all()
    else:
        rows = []
    return [offboarding_out(row) for row in rows]


@router.post("", response_model=EmployeeOffboardingOut)
def create_offboarding(
    payload: EmployeeOffboardingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "hr", "pm", "employee"})
    employee = target_employee(db, payload, user)
    existing = active_offboarding_for_employee(db, employee.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="active offboarding request already exists")

    final_month = payload.final_salary_month or month_from_date(payload.resignation_date)
    row = EmployeeOffboarding(
        employee_id=employee.id,
        full_name=employee.full_name,
        name_kana=employee.name_kana,
        email=employee.email,
        phone=employee.phone,
        residence=employee.residence,
        nearest_station=employee.nearest_station,
        employee_type=employee.employee_type,
        resignation_date=payload.resignation_date,
        last_work_date=payload.last_work_date,
        resignation_reason=payload.resignation_reason,
        reason_detail=payload.reason_detail,
        handover_note=payload.handover_note,
        final_salary_month=final_month,
        final_salary_hours=payload.final_salary_hours,
        final_salary_amount=payload.final_salary_amount,
        final_salary_note=payload.final_salary_note,
        status="pending",
        requester_id=user.id,
        attributes={"requested_by_role": user.role},
    )
    db.add(row)
    db.flush()
    workflow = WorkflowRequest(
        workflow_type="employee_offboarding",
        entity_type="employee_offboarding",
        entity_id=row.id,
        title=f"{row.full_name} offboarding",
        status="pending",
        requester_id=user.id,
        attributes={"employee_id": employee.id, "related_user_ids": [user.id]},
    )
    db.add(workflow)
    db.commit()
    db.refresh(row)
    return offboarding_out(row)


@router.get("/{offboarding_id}", response_model=EmployeeOffboardingOut)
def get_offboarding(
    offboarding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(EmployeeOffboarding, offboarding_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offboarding not found")
    if not can_access_offboarding(user, row):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    return offboarding_out(row)


@router.put("/{offboarding_id}", response_model=EmployeeOffboardingOut)
def update_offboarding(
    offboarding_id: int,
    payload: EmployeeOffboardingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "hr"})
    row = db.get(EmployeeOffboarding, offboarding_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offboarding not found")
    if row.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="completed offboarding cannot be edited")
    updates = payload.model_dump(exclude_unset=True)
    if "resignation_date" in updates and "final_salary_month" not in updates:
        updates["final_salary_month"] = month_from_date(updates["resignation_date"])
    for key, value in updates.items():
        setattr(row, key, value)
    employee = db.get(Employee, row.employee_id)
    if employee:
        snapshot_from_employee(row, employee)
    workflow = db.scalar(
        select(WorkflowRequest).where(
            WorkflowRequest.workflow_type == "employee_offboarding",
            WorkflowRequest.entity_type == "employee_offboarding",
            WorkflowRequest.entity_id == row.id,
        )
    )
    if workflow and row.status in {"pending", "cancelled", "rejected"}:
        workflow.status = row.status
        workflow.comment = "updated by HR/Admin" if row.status != "pending" else workflow.comment
    db.commit()
    db.refresh(row)
    return offboarding_out(row)


@router.delete("/{offboarding_id}")
def cancel_offboarding(
    offboarding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(EmployeeOffboarding, offboarding_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offboarding not found")
    if row.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only pending offboarding can be cancelled")
    if user.role not in {"admin", "hr"} and user.employee_id != row.employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    row.status = "cancelled"
    workflow = db.scalar(
        select(WorkflowRequest).where(
            WorkflowRequest.workflow_type == "employee_offboarding",
            WorkflowRequest.entity_type == "employee_offboarding",
            WorkflowRequest.entity_id == row.id,
        )
    )
    if workflow:
        workflow.status = "cancelled"
        workflow.comment = "cancelled"
    db.commit()
    return {"ok": True}
