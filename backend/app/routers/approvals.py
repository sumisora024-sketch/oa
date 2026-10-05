from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Employee, EmployeeOffboarding, ExternalDocument, Reimbursement, SalaryRecord, User, WorkflowRequest
from app.schemas import WorkflowDecisionIn, WorkflowRequestOut
from app.services.external_documents import public_document_url
from app.services.offboarding import approve_offboarding, offboarding_out
from app.services.salary import refresh_salary_records_for_employee
from app.services.workflow import can_process_workflow, decide_configured_workflow, reset_configured_workflow


router = APIRouter(prefix="/approvals", tags=["approvals"])


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
    if workflow.entity_type == "employee_profile_change":
        employee = db.get(Employee, workflow.entity_id)
        attrs = workflow.attributes or {}
        return {
            "id": employee.id if employee else workflow.entity_id,
            "employee_name": employee.full_name if employee else None,
            "before": attrs.get("before") or {},
            "changes": attrs.get("changes") or {},
            "reason": attrs.get("reason"),
        }
    return None


def workflow_out(db: Session, workflow: WorkflowRequest, user: User | None = None) -> dict:
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
        "can_process": can_process_workflow(user, workflow) if user else False,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
    }


def visible_to_user(user: User, workflow: WorkflowRequest) -> bool:
    return (
        user.role == "admin"
        or can_process_workflow(user, workflow)
        or workflow.requester_id == user.id
        or workflow.approver_id == user.id
    )


@router.get("", response_model=list[WorkflowRequestOut])
def list_approvals(
    workflow_type: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(WorkflowRequest).order_by(WorkflowRequest.created_at.desc())
    if workflow_type:
        stmt = stmt.where(WorkflowRequest.workflow_type == workflow_type)
    if status_filter:
        stmt = stmt.where(WorkflowRequest.status == status_filter)
    rows = [row for row in db.scalars(stmt).all() if visible_to_user(user, row)]
    return [workflow_out(db, row, user) for row in rows]


@router.get("/pending-count")
def pending_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    rows = list(db.scalars(select(WorkflowRequest).where(WorkflowRequest.status == "pending")).all())
    if user.role != "admin":
        rows = [row for row in rows if can_process_workflow(user, row)]
    return {"count": len(rows)}


@router.post("/{workflow_id}/decision", response_model=WorkflowRequestOut)
def decide_workflow(
    workflow_id: int,
    payload: WorkflowDecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = db.get(WorkflowRequest, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    if workflow.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="workflow already decided")

    terminal = decide_configured_workflow(db, workflow, user, payload.status, payload.comment)
    if not terminal:
        db.commit()
        db.refresh(workflow)
        return workflow_out(db, workflow, user)
    approved = workflow.status == "approved"

    if workflow.workflow_type in {"partner_quotation", "partner_invoice"} and workflow.entity_type == "external_document":
        document = db.get(ExternalDocument, workflow.entity_id)
        if document:
            attrs = dict(document.attributes or {})
            attrs["approval_status"] = workflow.status
            attrs["approval_comment"] = payload.comment
            attrs["approved_by"] = user.id
            attrs["approved_at"] = workflow.decided_at.isoformat() if workflow.decided_at else None
            document.attributes = attrs
    if workflow.workflow_type == "reimbursement" and workflow.entity_type == "reimbursement":
        row = db.get(Reimbursement, workflow.entity_id)
        if row:
            row.status = workflow.status
            row.approver_id = user.id if approved else None
            row.approved_at = workflow.decided_at if approved else None
            db.flush()
            attrs = dict(row.attributes or {})
            attrs.pop("salary_locked_warning", None)
            if approved:
                salary = db.scalar(
                    select(SalaryRecord).where(
                        SalaryRecord.employee_id == row.employee_id,
                        SalaryRecord.year_month == row.pay_month,
                    )
                )
                if salary and salary.locked:
                    attrs["salary_locked_warning"] = "支給月の給与がロックされているため自動反映されません"
                else:
                    refresh_salary_records_for_employee(
                        db,
                        row.employee_id,
                        months={row.pay_month},
                        include_current=False,
                        reason="reimbursement_approval_changed",
                    )
            row.attributes = attrs
    if workflow.workflow_type == "employee_offboarding" and workflow.entity_type == "employee_offboarding":
        row = db.get(EmployeeOffboarding, workflow.entity_id)
        if row:
            if approved:
                approve_offboarding(db, row, user)
            else:
                row.status = "rejected"
                row.approver_id = user.id
                row.approved_at = workflow.decided_at
    if workflow.workflow_type == "employee_profile_change" and workflow.entity_type == "employee_profile_change" and approved:
        employee = db.get(Employee, workflow.entity_id)
        if employee:
            changes = dict((workflow.attributes or {}).get("changes") or {})
            new_email = changes.get("email")
            if new_email:
                duplicate = db.scalar(select(Employee.id).where(Employee.email == new_email, Employee.id != employee.id))
                if duplicate:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同じメールアドレスの社員が登録されています")
            if isinstance(changes.get("birth_date"), str):
                changes["birth_date"] = date.fromisoformat(changes["birth_date"])
            for key, value in changes.items():
                if key in {"full_name", "name_kana", "birth_date", "graduation_status", "residence", "email", "nationality"}:
                    setattr(employee, key, value)
            if "full_name" in changes and employee.user:
                employee.user.full_name = employee.full_name
            if "birth_date" in changes:
                sync = refresh_salary_records_for_employee(
                    db, employee.id, reason="employee_profile_birth_date_approved"
                )
                attrs = dict(workflow.attributes or {})
                attrs["salary_sync"] = sync
                if sync["locked_months"]:
                    attrs["salary_locked_warning"] = f"給与がロックされています: {', '.join(sync['locked_months'])}"
                else:
                    attrs.pop("salary_locked_warning", None)
                workflow.attributes = attrs

    db.commit()
    db.refresh(workflow)
    return workflow_out(db, workflow, user)


@router.post("/{workflow_id}/withdraw", response_model=WorkflowRequestOut)
def withdraw_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = db.get(WorkflowRequest, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    if not can_process_workflow(user, workflow):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="権限不足")
    if workflow.status != "approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only approved workflow can be withdrawn")

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
            db.flush()
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
                refresh_salary_records_for_employee(
                    db,
                    row.employee_id,
                    months={row.pay_month},
                    include_current=False,
                    reason="reimbursement_approval_withdrawn",
                )
            row.attributes = attrs
    if workflow.workflow_type == "employee_offboarding" and workflow.entity_type == "employee_offboarding":
        row = db.get(EmployeeOffboarding, workflow.entity_id)
        if row:
            if row.status == "completed":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="completed offboarding cannot be withdrawn")
            row.status = "pending"
            row.approver_id = None
            row.approved_at = None
            db.flush()
            sync = refresh_salary_records_for_employee(
                db,
                row.employee_id,
                months={row.final_salary_month},
                include_current=False,
                reason="offboarding_approval_withdrawn",
            )
            attrs = dict(row.attributes or {})
            if sync["locked_months"]:
                attrs["salary_locked_warning"] = f"給与がロックされています: {', '.join(sync['locked_months'])}"
            else:
                attrs.pop("salary_locked_warning", None)
            attrs["salary_sync"] = sync
            row.attributes = attrs
    if workflow.workflow_type == "employee_profile_change" and workflow.entity_type == "employee_profile_change":
        employee = db.get(Employee, workflow.entity_id)
        if employee:
            attrs = workflow.attributes or {}
            changes = dict(attrs.get("changes") or {})
            before = dict(attrs.get("before") or {})
            for key, approved_value in changes.items():
                current_value = getattr(employee, key, None)
                comparable = current_value.isoformat() if hasattr(current_value, "isoformat") else current_value
                if comparable != approved_value:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="承認後に個人情報が変更されているため撤回できません")
            if isinstance(before.get("birth_date"), str):
                before["birth_date"] = date.fromisoformat(before["birth_date"])
            for key, value in before.items():
                if key in {"full_name", "name_kana", "birth_date", "graduation_status", "residence", "email", "nationality"}:
                    setattr(employee, key, value)
            if "full_name" in before and employee.user:
                employee.user.full_name = employee.full_name
            if "birth_date" in before:
                sync = refresh_salary_records_for_employee(
                    db, employee.id, reason="employee_profile_birth_date_withdrawn"
                )
                workflow_attrs = dict(workflow.attributes or {})
                workflow_attrs["salary_sync"] = sync
                if sync["locked_months"]:
                    workflow_attrs["salary_locked_warning"] = f"給与がロックされています: {', '.join(sync['locked_months'])}"
                else:
                    workflow_attrs.pop("salary_locked_warning", None)
                workflow.attributes = workflow_attrs

    reset_configured_workflow(workflow, user)
    db.commit()
    db.refresh(workflow)
    return workflow_out(db, workflow, user)
