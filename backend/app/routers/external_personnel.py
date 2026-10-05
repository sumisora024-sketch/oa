import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import BusinessPartner, ExternalDocument, ExternalPersonnel, User
from app.schemas import ExternalPersonnelOut, ExternalPersonnelStatusIn, ExternalPersonnelUpdate
from app.services.external_documents import safe_filename

router = APIRouter(prefix="/external-personnel", tags=["external_personnel"])

PERSONNEL_DIR = ROOT_DIR / "backend" / "storage" / "external_personnel"


def ensure_personnel_dir() -> None:
    PERSONNEL_DIR.mkdir(parents=True, exist_ok=True)


def ensure_internal_personnel_user(user: User) -> None:
    ensure_role(user, {"admin", "soumu", "hr"})


def personnel_file_url(row_id: int, kind: str, path: str | None) -> str | None:
    return f"/api/external-personnel/{row_id}/files/{kind}/download" if path else None


def personnel_out(row: ExternalPersonnel) -> dict:
    return {
        "id": row.id,
        "partner_id": row.partner_id,
        "partner_name": row.partner.company_name if row.partner else row.company_name,
        "full_name": row.full_name,
        "company_name": row.company_name,
        "assignment_month": row.assignment_month,
        "contract_end_date": row.contract_end_date,
        "monthly_hours": row.monthly_hours,
        "resume_download_url": personnel_file_url(row.id, "resume", row.resume_path),
        "avatar_download_url": personnel_file_url(row.id, "avatar", row.avatar_path),
        "timesheet_download_url": personnel_file_url(row.id, "timesheet", row.timesheet_path),
        "status": row.status,
        "note": row.note,
        "attributes": row.attributes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def can_access_personnel(user: User, row: ExternalPersonnel) -> bool:
    if user.role in {"admin", "soumu", "hr"}:
        return True
    return user.role == "partner" and user.partner_id == row.partner_id


def get_personnel_or_404(db: Session, personnel_id: int, user: User) -> ExternalPersonnel:
    row = db.get(ExternalPersonnel, personnel_id)
    if not row or row.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="external personnel not found")
    if not can_access_personnel(user, row):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    return row


def get_partner_for_submit(db: Session, user: User, partner_id: int | None) -> BusinessPartner:
    if user.role == "partner":
        if not user.partner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="partner account is not linked")
        partner = db.get(BusinessPartner, user.partner_id)
    else:
        ensure_internal_personnel_user(user)
        if not partner_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="partner_id is required")
        partner = db.get(BusinessPartner, partner_id)
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="partner not found")
    return partner


def has_approved_partner_quotation(db: Session, partner_id: int, assignment_month: str) -> bool:
    rows = db.scalars(
        select(ExternalDocument).where(
            ExternalDocument.partner_id == partner_id,
            ExternalDocument.document_type == "partner_quotation",
        )
    ).all()
    for row in rows:
        attrs = row.attributes or {}
        start_month = attrs.get("target_start_month") or row.target_month
        end_month = attrs.get("target_end_month") or row.target_month
        if attrs.get("approval_status") == "approved" and start_month <= assignment_month <= end_month:
            return True
    return False


def save_upload(file: UploadFile | None, prefix: str, partner_name: str, full_name: str) -> str | None:
    if not file or not file.filename:
        return None
    ensure_personnel_dir()
    filename = safe_filename(f"{prefix}_{partner_name}_{full_name}_{file.filename}")
    path = PERSONNEL_DIR / filename
    with path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return str(path)


@router.get("", response_model=list[ExternalPersonnelOut])
def list_external_personnel(
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in {"admin", "soumu", "hr", "partner"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    stmt = select(ExternalPersonnel).where(ExternalPersonnel.status != "deleted").order_by(ExternalPersonnel.created_at.desc())
    if user.role == "partner":
        stmt = stmt.where(ExternalPersonnel.partner_id == user.partner_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(ExternalPersonnel.full_name.like(like), ExternalPersonnel.company_name.like(like)))
    return [personnel_out(row) for row in db.scalars(stmt).all()]


@router.post("", response_model=ExternalPersonnelOut)
def create_external_personnel(
    full_name: str = Form(...),
    assignment_month: str = Form(...),
    contract_end_date: str | None = Form(None),
    monthly_hours: float | None = Form(None),
    note: str | None = Form(None),
    partner_id: int | None = Form(None),
    resume: UploadFile | None = File(None),
    avatar: UploadFile | None = File(None),
    timesheet: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in {"admin", "soumu", "hr", "partner"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    partner = get_partner_for_submit(db, user, partner_id)
    if user.role == "partner" and not has_approved_partner_quotation(db, partner.id, assignment_month):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="approved quotation is required before personnel submission")
    if not resume or not resume.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CV is required")
    if not avatar or not avatar.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PNG avatar is required")
    if not avatar.filename.lower().endswith(".png"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="avatar must be a PNG file")

    parsed_end = datetime.strptime(contract_end_date, "%Y-%m-%d").date() if contract_end_date else None
    row = ExternalPersonnel(
        partner_id=partner.id,
        full_name=full_name.strip(),
        company_name=partner.company_name,
        assignment_month=assignment_month,
        contract_end_date=parsed_end,
        monthly_hours=monthly_hours,
        note=note,
        status="submitted",
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    row.resume_path = save_upload(resume, "resume", partner.company_name, row.full_name)
    row.avatar_path = save_upload(avatar, "avatar", partner.company_name, row.full_name)
    row.timesheet_path = save_upload(timesheet, "timesheet", partner.company_name, row.full_name)
    db.commit()
    db.refresh(row)
    return personnel_out(row)


@router.put("/{personnel_id}", response_model=ExternalPersonnelOut)
def update_external_personnel(
    personnel_id: int,
    payload: ExternalPersonnelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_internal_personnel_user(user)
    row = get_personnel_or_404(db, personnel_id, user)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return personnel_out(row)


@router.post("/{personnel_id}/status", response_model=ExternalPersonnelOut)
def update_personnel_status(
    personnel_id: int,
    payload: ExternalPersonnelStatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_internal_personnel_user(user)
    row = get_personnel_or_404(db, personnel_id, user)
    row.status = payload.status
    row.note = payload.note if payload.note is not None else row.note
    row.confirmed_by = user.id
    row.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return personnel_out(row)


@router.delete("/{personnel_id}")
def delete_external_personnel(personnel_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_internal_personnel_user(user)
    row = get_personnel_or_404(db, personnel_id, user)
    row.status = "deleted"
    db.commit()
    return {"ok": True}


@router.get("/{personnel_id}/files/{kind}/download")
def download_personnel_file(personnel_id: int, kind: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = get_personnel_or_404(db, personnel_id, user)
    path_map = {
        "resume": row.resume_path,
        "avatar": row.avatar_path,
        "timesheet": row.timesheet_path,
    }
    if kind not in path_map or not path_map[kind]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    path = Path(path_map[kind])
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    return FileResponse(path, filename=path.name)
