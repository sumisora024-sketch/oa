from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.db import get_db
from app.deps import get_current_user
from app.models import Employee, Reimbursement, User, WorkflowRequest
from app.schemas import REIMBURSEMENT_TYPES, ReimbursementOut, ReimbursementUpdate
from app.services.external_documents import safe_filename
from app.services.workflow import create_workflow_request

router = APIRouter(prefix="/reimbursements", tags=["reimbursements"])

REIMBURSEMENT_DIR = ROOT_DIR / "backend" / "storage" / "reimbursements"


def next_month(value: date | None = None) -> str:
    current = value or date.today()
    year = current.year + (1 if current.month == 12 else 0)
    month = 1 if current.month == 12 else current.month + 1
    return f"{year}-{month:02d}"


def can_manage_all(user: User) -> bool:
    return user.role in {"admin", "soumu", "hr"}


def ensure_visible(user: User, reimbursement: Reimbursement) -> None:
    if can_manage_all(user):
        return
    if user.role in {"pm", "employee"} and user.employee_id == reimbursement.employee_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


def ensure_mutable(user: User, reimbursement: Reimbursement) -> None:
    ensure_visible(user, reimbursement)
    if reimbursement.status == "approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="承認済みの経費精算はロックされています")


def month_range_ok(start: str, end: str) -> None:
    if end < start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="終了月は開始月以降にしてください")


def file_links(row: Reimbursement) -> list[dict]:
    links = []
    for index, item in enumerate(row.invoice_file_paths or []):
        name = item.get("name") if isinstance(item, dict) else Path(str(item)).name
        links.append({"name": name, "download_url": f"/api/reimbursements/{row.id}/files/{index}/download"})
    return links


def reimbursement_out(row: Reimbursement) -> dict:
    return {
        "id": row.id,
        "expense_type": row.expense_type,
        "period_start_month": row.period_start_month,
        "period_end_month": row.period_end_month,
        "employee_id": row.employee_id,
        "employee_name": row.employee.full_name if row.employee else None,
        "amount": row.amount,
        "pay_month": row.pay_month,
        "status": row.status,
        "invoice_file_paths": row.invoice_file_paths,
        "invoice_files": file_links(row),
        "note": row.note,
        "requester_id": row.requester_id,
        "requester_name": row.requester.full_name if row.requester else None,
        "approver_id": row.approver_id,
        "approver_name": row.approver.full_name if row.approver else None,
        "approved_at": row.approved_at,
        "attributes": row.attributes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def validate_expense_type(value: str) -> str:
    if value not in REIMBURSEMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="経費種別はリストから選択してください")
    return value


def save_files(row_id: int, files: list[UploadFile] | None) -> list[dict]:
    saved: list[dict] = []
    if not files:
        return saved
    target_dir = REIMBURSEMENT_DIR / str(row_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    for index, file in enumerate(files):
        filename = safe_filename(file.filename or f"receipt-{index + 1}")
        path = target_dir / f"{index + 1}-{filename}"
        with path.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                output.write(chunk)
        saved.append({"name": file.filename or filename, "path": str(path)})
    return saved


@router.get("", response_model=list[ReimbursementOut])
def list_reimbursements(
    q: str | None = None,
    status_filter: str | None = None,
    pay_month: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "partner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    stmt = select(Reimbursement).order_by(Reimbursement.created_at.desc())
    if not can_manage_all(user):
        if user.role not in {"pm", "employee"} or not user.employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        stmt = stmt.where(Reimbursement.employee_id == user.employee_id)
    if status_filter:
        stmt = stmt.where(Reimbursement.status == status_filter)
    if pay_month:
        stmt = stmt.where(Reimbursement.pay_month == pay_month)
    if q:
        like = f"%{q}%"
        stmt = stmt.join(Employee).where(or_(Employee.full_name.like(like), Reimbursement.expense_type.like(like), Reimbursement.note.like(like)))
    return [reimbursement_out(row) for row in db.scalars(stmt).all()]


@router.post("", response_model=ReimbursementOut)
def create_reimbursement(
    expense_type: str = Form(...),
    period_start_month: str = Form(...),
    period_end_month: str | None = Form(None),
    employee_id: int | None = Form(None),
    amount: int = Form(...),
    pay_month: str | None = Form(None),
    note: str | None = Form(None),
    files: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "partner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    validate_expense_type(expense_type)
    target_employee_id = employee_id if can_manage_all(user) and employee_id else user.employee_id
    if not target_employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="報销人员不能为空")
    employee = db.get(Employee, target_employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    end_month = period_end_month or period_start_month
    month_range_ok(period_start_month, end_month)
    row = Reimbursement(
        expense_type=expense_type,
        period_start_month=period_start_month,
        period_end_month=end_month,
        employee_id=employee.id,
        amount=amount,
        pay_month=pay_month or next_month(),
        status="pending",
        note=note,
        requester_id=user.id,
    )
    db.add(row)
    db.flush()
    row.invoice_file_paths = save_files(row.id, files)
    create_workflow_request(
        db,
        workflow_type="reimbursement",
        entity_type="reimbursement",
        entity_id=row.id,
        title=f"経費精算申請 - {employee.full_name} - {row.pay_month}",
        requester_id=user.id,
        attributes={"related_user_ids": [user.id], "employee_id": employee.id},
        link="/approvals/reimbursements",
    )
    db.commit()
    db.refresh(row)
    return reimbursement_out(row)


@router.put("/{reimbursement_id}", response_model=ReimbursementOut)
def update_reimbursement(
    reimbursement_id: int,
    payload: ReimbursementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(Reimbursement, reimbursement_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="経費精算が存在しません")
    ensure_mutable(user, row)
    updates = payload.model_dump(exclude_unset=True)
    if "expense_type" in updates and updates["expense_type"]:
        validate_expense_type(updates["expense_type"])
    if "employee_id" in updates and not can_manage_all(user):
        updates.pop("employee_id")
    for key, value in updates.items():
        if value is not None:
            setattr(row, key, value)
    if not row.period_end_month:
        row.period_end_month = row.period_start_month
    month_range_ok(row.period_start_month, row.period_end_month)
    db.commit()
    db.refresh(row)
    return reimbursement_out(row)


@router.delete("/{reimbursement_id}")
def delete_reimbursement(
    reimbursement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(Reimbursement, reimbursement_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="経費精算が存在しません")
    ensure_mutable(user, row)
    workflows = db.scalars(
        select(WorkflowRequest).where(WorkflowRequest.entity_type == "reimbursement", WorkflowRequest.entity_id == row.id)
    ).all()
    for workflow in workflows:
        workflow.status = "rejected"
        workflow.comment = "deleted"
        workflow.decided_at = datetime.utcnow()
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/{reimbursement_id}/files/{file_index}/download")
def download_reimbursement_file(
    reimbursement_id: int,
    file_index: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(Reimbursement, reimbursement_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="経費精算が存在しません")
    ensure_visible(user, row)
    files = row.invoice_file_paths or []
    if file_index < 0 or file_index >= len(files):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ファイルが存在しません")
    item = files[file_index]
    path = Path(item.get("path") if isinstance(item, dict) else str(item))
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ファイルが存在しません")
    filename = item.get("name") if isinstance(item, dict) else path.name
    return FileResponse(path, filename=filename)
