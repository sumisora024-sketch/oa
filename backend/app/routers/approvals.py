from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import EmployeeOffboarding, ExternalDocument, Reimbursement, SalaryRecord, User, WorkflowRequest
from app.schemas import WorkflowDecisionIn, WorkflowRequestOut
from app.services.external_documents import public_document_url
from app.services.offboarding import approve_offboarding, offboarding_out
from app.services.salary import refresh_salary_record_for_employee

router = APIRouter(prefix="/approvals", tags=["approvals"])


def ensure_approver(user: User) -> None:
    ensure_role(user, {"admin", "hr", "pm"})


def workflow_entity(db: Session, workflow: WorkflowRequest) -> dict | None:
    if workflow.entity_type == "external_document":
        document = db.get(ExternalDocument, workflow.entity_id)
        if not document:
            return None
        return {
            "id": document.id,
            "partner_id": document.partner_id,
            "partner_name": document.partner.company_name if document.partner else None,
            "document_type": document.document_type,
            "document_no": document.document_no,
            "target_month": document.target_month,
            "issue_date": document.issue_date,
            "subtotal": document.subtotal,
            "tax": document.tax,
            "total": document.total,
            "items": document.items,
            "note": document.note,
            "attributes": document.attributes,
            "download_url": public_document_url(document.id) if document.file_path else None,
        }
    if workflow.entity_type == "reimbursement":
        row = db.get(Reimbursement, workflow.entity_id)
        if not row:
            return None
        files = [
            {
                "name": item.get("name") if isinstance(item, dict) else str(index + 1),
                "download_url": f"/api/reimbursements/{row.id}/files/{index}/download",
            }
            for index, item in enumerate(row.invoice_file_paths or [])
        ]
        return {
            "id": row.id,
            "expense_type": row.expense_type,
            "employee_id": row.employee_id,
            "employee_name": row.employee.full_name if row.employee else None,
            "period_start_month": row.period_start_month,
            "period_end_month": row.period_end_month,
            "pay_month": row.pay_month,
            "total": row.amount,
            "note": row.note,
            "status": row.status,
            "files": files,
            "attributes": row.attributes,
        }
    if workflow.entity_type == "employee_offboarding":
        row = db.get(EmployeeOffboarding, workflow.entity_id)
        return offboarding_out(row) if row else None
    return None


def is_related_to_pm(user: User, workflow: WorkflowRequest) -> bool:
    if workflow.requester_id == user.id or workflow.approver_id == user.id:
        return True
    attrs = workflow.attributes or {}
    related = attrs.get("related_user_ids") or []
    return user.id in related


def workflow_out(db: Session, workflow: WorkflowRequest) -> dict:
    return {
        "id": workflow.id,
        "workflow_type": workflow.workflow_type,
        "entity_type": workflow.entity_type,
        "entity_id": workflow.entity_id,
        "title": workflow.title,
        "status": workflow.status,
        "requester_id": workflow.requester_id,
        "requester_name": workflow.requester.full_name if workflow.requester else None,
        "approver_id": workflow.approver_id,
        "approver_name": workflow.approver.full_name if workflow.approver else None,
        "submitted_at": workflow.submitted_at,
        "decided_at": workflow.decided_at,
        "comment": workflow.comment,
        "attributes": workflow.attributes,
        "entity": workflow_entity(db, workflow),
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
    }


@router.get("", response_model=list[WorkflowRequestOut])
def list_approvals(
    workflow_type: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_approver(user)
    stmt = select(WorkflowRequest).order_by(WorkflowRequest.created_at.desc())
    if workflow_type:
        stmt = stmt.where(WorkflowRequest.workflow_type == workflow_type)
    if status_filter:
        stmt = stmt.where(WorkflowRequest.status == status_filter)
    rows = list(db.scalars(stmt).all())
    if user.role == "pm":
        rows = [row for row in rows if row.workflow_type != "reimbursement" and is_related_to_pm(user, row)]
    return [workflow_out(db, row) for row in rows]


@router.get("/pending-count")
def pending_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    ensure_approver(user)
    rows = list(db.scalars(select(WorkflowRequest).where(WorkflowRequest.status == "pending")).all())
    if user.role == "pm":
        rows = [row for row in rows if row.workflow_type != "reimbursement" and is_related_to_pm(user, row)]
    return {"count": len(rows)}


@router.post("/{workflow_id}/decision", response_model=WorkflowRequestOut)
def decide_workflow(
    workflow_id: int,
    payload: WorkflowDecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_approver(user)
    workflow = db.get(WorkflowRequest, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    if user.role == "pm" and (workflow.workflow_type == "reimbursement" or not is_related_to_pm(user, workflow)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    if workflow.workflow_type == "employee_offboarding" and user.role not in {"admin", "hr"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    if workflow.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="workflow already decided")

    workflow.status = payload.status
    workflow.comment = payload.comment
    workflow.approver_id = user.id
    workflow.decided_at = datetime.utcnow()

    if workflow.workflow_type in {"partner_quotation", "partner_invoice"} and workflow.entity_type == "external_document":
        document = db.get(ExternalDocument, workflow.entity_id)
        if document:
            attrs = dict(document.attributes or {})
            attrs["approval_status"] = payload.status
            attrs["approval_comment"] = payload.comment
            attrs["approved_by"] = user.id
            attrs["approved_at"] = workflow.decided_at.isoformat()
            document.attributes = attrs
    if workflow.workflow_type == "reimbursement" and workflow.entity_type == "reimbursement":
        row = db.get(Reimbursement, workflow.entity_id)
        if row:
            row.status = payload.status
            row.approver_id = user.id if payload.status == "approved" else None
            row.approved_at = workflow.decided_at if payload.status == "approved" else None
            attrs = dict(row.attributes or {})
            attrs.pop("salary_locked_warning", None)
            if payload.status == "approved":
                salary = db.scalar(
                    select(SalaryRecord).where(
                        SalaryRecord.employee_id == row.employee_id,
                        SalaryRecord.year_month == row.pay_month,
                    )
                )
                if salary and salary.locked:
                    attrs["salary_locked_warning"] = "支給月の給与がロックされているため自動反映されません"
                else:
                    refresh_salary_record_for_employee(db, row.employee_id, row.pay_month)
            row.attributes = attrs
    if workflow.workflow_type == "employee_offboarding" and workflow.entity_type == "employee_offboarding":
        row = db.get(EmployeeOffboarding, workflow.entity_id)
        if row:
            if payload.status == "approved":
                approve_offboarding(db, row, user)
            else:
                row.status = "rejected"
                row.approver_id = user.id
                row.approved_at = workflow.decided_at

    db.commit()
    db.refresh(workflow)
    return workflow_out(db, workflow)


@router.post("/{workflow_id}/withdraw", response_model=WorkflowRequestOut)
def withdraw_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_approver(user)
    workflow = db.get(WorkflowRequest, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    if user.role == "pm" and (workflow.workflow_type == "reimbursement" or not is_related_to_pm(user, workflow)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    if workflow.workflow_type == "employee_offboarding" and user.role not in {"admin", "hr"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    if workflow.status != "approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only approved workflow can be withdrawn")

    workflow.status = "pending"
    workflow.comment = None
    workflow.approver_id = None
    workflow.decided_at = None

    if workflow.workflow_type in {"partner_quotation", "partner_invoice"} and workflow.entity_type == "external_document":
        document = db.get(ExternalDocument, workflow.entity_id)
        if document:
            attrs = dict(document.attributes or {})
            attrs["approval_status"] = "pending"
            attrs.pop("approval_comment", None)
            attrs.pop("approved_by", None)
            attrs.pop("approved_at", None)
            document.attributes = attrs
    if workflow.workflow_type == "reimbursement" and workflow.entity_type == "reimbursement":
        row = db.get(Reimbursement, workflow.entity_id)
        if row:
            row.status = "pending"
            row.approver_id = None
            row.approved_at = None
            attrs = dict(row.attributes or {})
            attrs.pop("salary_locked_warning", None)
            salary = db.scalar(
                select(SalaryRecord).where(
                    SalaryRecord.employee_id == row.employee_id,
                    SalaryRecord.year_month == row.pay_month,
                )
            )
            if salary and salary.locked:
                attrs["salary_locked_warning"] = "支給月の給与がロックされているため自動反映されません"
            else:
                refresh_salary_record_for_employee(db, row.employee_id, row.pay_month)
            row.attributes = attrs
    if workflow.workflow_type == "employee_offboarding" and workflow.entity_type == "employee_offboarding":
        row = db.get(EmployeeOffboarding, workflow.entity_id)
        if row:
            if row.status == "completed":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="completed offboarding cannot be withdrawn")
            row.status = "pending"
            row.approver_id = None
            row.approved_at = None

    db.commit()
    db.refresh(workflow)
    return workflow_out(db, workflow)
