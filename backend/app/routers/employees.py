from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import can_read_employee, can_update_employee, ensure_role
from app.core.security import get_password_hash
from app.db import get_db
from app.deps import get_current_user
from app.models import Employee, User, WorkflowRequest
from app.schemas import EmployeeCreate, EmployeeOut, EmployeeProfileChangeIn, EmployeeSelfUpdate, EmployeeUpdate, WorkflowRequestOut
from app.services.offboarding import create_immediate_offboarding
from app.services.salary import refresh_salary_records_for_employee
from app.services.accounts import ensure_employee_user
from app.services.xlsx_import import import_employees_from_xlsx
from app.services.workflow import create_workflow_request

router = APIRouter(prefix="/employees", tags=["employees"])

SELF_EDITABLE_FIELDS = {
    "phone",
    "nearest_station",
    "languages",
    "certifications",
    "technical_experience",
    "it_years",
    "talent_category",
    "skills",
}


def calculate_age(birth_date):
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def role_from_employee_type(employee_type: str | None) -> str:
    text = (employee_type or "").strip().lower()
    if text == "hr":
        return "hr"
    if "総務" in text or "soumu" in text:
        return "soumu"
    if "admin" in text or "\u7ba1\u7406" in text or "管理" in text:
        return "admin"
    if "pm" in text or "sales" in text or "\u8425\u4e1a" in text or "営業" in text:
        return "pm"
    return "employee"


@router.get("", response_model=list[EmployeeOut])
def list_employees(q: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in {"admin", "soumu", "hr", "pm"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    stmt = select(Employee).where(Employee.is_deleted.is_(False)).order_by(Employee.created_at.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Employee.full_name.like(like), Employee.name_kana.like(like), Employee.email.like(like), Employee.talent_category.like(like)))
    return list(db.scalars(stmt).all())


@router.post("", response_model=EmployeeOut)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    existing = db.scalar(select(Employee).where(Employee.email == payload.email))
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同一姓名和邮箱的人员已存在")
    data = payload.model_dump()
    skills = [item.model_dump() for item in payload.skills]
    data.pop("skills", None)
    restored = existing is not None
    if restored:
        employee = existing
        for key, value in data.items():
            setattr(employee, key, value)
        employee.is_deleted = False
        employee.deleted_at = None
    else:
        employee = Employee(**data)
    employee.employee_type = employee.employee_type or "一般社員"
    employee.skills = skills
    employee.age = calculate_age(employee.birth_date)
    if not restored:
        db.add(employee)
        db.flush()
    linked_user = ensure_employee_user(db, employee, must_reset_password=True)
    linked_user.role = role_from_employee_type(employee.employee_type)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/me/employment-info/download")
def download_my_employment_info(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未绑定人员信息")
    return download_employment_info(user.employee_id, db, user)


@router.get("/me", response_model=EmployeeOut)
def get_my_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社員情報が紐付いていません")
    employee = db.get(Employee, user.employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社員情報が見つかりません")
    return employee


@router.patch("/me", response_model=EmployeeOut)
def update_my_profile(
    payload: EmployeeSelfUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社員情報が紐付いていません")
    employee = db.get(Employee, user.employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社員情報が見つかりません")
    updates = payload.model_dump(exclude_unset=True)
    if "skills" in updates and updates["skills"] is not None:
        updates["skills"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in payload.skills or []]
    for key, value in updates.items():
        setattr(employee, key, value)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/me/change-requests", response_model=list[WorkflowRequestOut])
def list_my_profile_change_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = list(
        db.scalars(
            select(WorkflowRequest)
            .where(
                WorkflowRequest.workflow_type == "employee_profile_change",
                WorkflowRequest.requester_id == user.id,
            )
            .order_by(WorkflowRequest.created_at.desc())
        ).all()
    )
    return rows


@router.post("/me/change-requests", response_model=WorkflowRequestOut)
def create_my_profile_change_request(
    payload: EmployeeProfileChangeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社員情報が紐付いていません")
    employee = db.get(Employee, user.employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社員情報が見つかりません")
    existing = db.scalar(
        select(WorkflowRequest.id).where(
            WorkflowRequest.workflow_type == "employee_profile_change",
            WorkflowRequest.entity_id == employee.id,
            WorkflowRequest.status == "pending",
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="処理中の個人情報変更申請があります")
    changes = payload.model_dump(exclude_unset=True, mode="json")
    reason = changes.pop("reason", None)
    before = {
        key: value.isoformat() if hasattr((value := getattr(employee, key)), "isoformat") else value
        for key in changes
    }
    workflow = create_workflow_request(
        db,
        workflow_type="employee_profile_change",
        entity_type="employee_profile_change",
        entity_id=employee.id,
        title=f"個人情報変更申請: {employee.full_name}",
        requester_id=user.id,
        attributes={"before": before, "changes": changes, "reason": reason, "related_user_ids": [user.id]},
        link="/approvals/contracts",
    )
    db.commit()
    db.refresh(workflow)
    return workflow


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    if not can_read_employee(user, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return employee


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, payload: EmployeeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    if not can_update_employee(user, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    updates = payload.model_dump(exclude_unset=True)
    if user.role not in {"admin", "soumu", "hr"}:
        updates = {key: value for key, value in updates.items() if key in SELF_EDITABLE_FIELDS}
    if "employee_type" in updates and user.role != "admin":
        updates.pop("employee_type")
    if user.role not in {"admin", "soumu", "hr"}:
        updates.pop("estimated_annual_salary", None)
        updates.pop("estimated_annual_salary_manual", None)
    if "estimated_annual_salary" in updates and "estimated_annual_salary_manual" not in updates:
        updates["estimated_annual_salary_manual"] = updates["estimated_annual_salary"] is not None
    if "skills" in updates and updates["skills"] is not None:
        updates["skills"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in payload.skills or []]
    for key, value in updates.items():
        setattr(employee, key, value)
    if "birth_date" in updates:
        employee.age = calculate_age(employee.birth_date)
        employee.salary_sync = refresh_salary_records_for_employee(
            db,
            employee.id,
            months=None,
            include_current=True,
            reason="employee_birth_date_changed",
        )
    if user.role == "admin":
        linked_user = ensure_employee_user(db, employee, must_reset_password=True)
        if "employee_type" in updates:
            linked_user.role = role_from_employee_type(employee.employee_type)
    db.commit()
    db.refresh(employee)
    return employee


@router.post("/{employee_id}/password/reset")
def reset_employee_password(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    linked_user = ensure_employee_user(db, employee, must_reset_password=True)
    settings = get_settings()
    linked_user.password_hash = get_password_hash(settings.default_employee_password)
    linked_user.must_reset_password = True
    linked_user.is_active = True
    db.commit()
    return {"ok": True, "email": linked_user.email}


@router.delete("/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    create_immediate_offboarding(db, employee, user)
    db.commit()
    return {"ok": True}


@router.post("/import-xlsx")
def import_xlsx(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in {"admin", "soumu", "hr"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 xlsx 文件")
    result = import_employees_from_xlsx(file.file, db)
    if result["created"] == 0 and result["updated"] == 0 and result.get("errors"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["errors"])
    return result


@router.get("/{employee_id}/employment-info/download")
def download_employment_info(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    if not can_read_employee(user, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    content = "\n".join(
        [
            "在职信息",
            f"姓名: {employee.full_name}",
            f"日文假名: {employee.name_kana or ''}",
            f"邮箱: {employee.email}",
            f"电话: {employee.phone or ''}",
            f"居住地: {employee.residence or ''}",
            f"最近车站: {employee.nearest_station or ''}",
            f"人才分类: {employee.talent_category or ''}",
            f"IT年数: {employee.it_years or ''}",
        ]
    )
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=employment-{employee.id}.txt"},
    )
