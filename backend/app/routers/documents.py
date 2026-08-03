import hashlib
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import DocumentArchive, ExternalDocument, ExternalPersonnel, PartnerOnboardingItem, Reimbursement, User
from app.routers.external import document_deleted, public_document_url

router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_ROOT = ROOT_DIR / "backend" / "storage"
SCAN_DIRECTORIES = {"external_documents", "external_uploads", "external_personnel", "reimbursements", "subcontracting"}


def hidden_keys(container: object) -> set[str]:
    attrs = getattr(container, "attributes", None) or getattr(container, "form_data", None) or {}
    values = attrs.get("hidden_document_keys") if isinstance(attrs, dict) else None
    return set(values or [])


def add_hidden_key(container: object, key: str) -> None:
    attr_name = "attributes" if hasattr(container, "attributes") else "form_data"
    attrs = dict(getattr(container, attr_name, None) or {})
    values = set(attrs.get("hidden_document_keys") or [])
    values.add(key)
    attrs["hidden_document_keys"] = sorted(values)
    setattr(container, attr_name, attrs)


def file_name(path_or_name: str | None) -> str:
    if not path_or_name:
        return "-"
    return Path(path_or_name).name


def archive_download_url(row_id: int) -> str:
    return f"/api/documents/archive/{row_id}/download"


def storage_path(value: str | Path | None) -> str | None:
    if not value:
        return None
    return str(Path(value))


def directory_for(path_value: str | None) -> str | None:
    if not path_value:
        return None
    try:
        path = Path(path_value)
        return str(path.parent.relative_to(STORAGE_ROOT))
    except ValueError:
        return str(Path(path_value).parent)


def guess_document_type(path: Path) -> str:
    name = path.name.lower()
    parent = path.parent.name.lower()
    if "reimbursement" in str(path).lower():
        return "reimbursement"
    if "resume" in name:
        return "resume"
    if "avatar" in name or "顔" in name:
        return "avatar"
    if "timesheet" in name or "勤務" in name:
        return "timesheet"
    if "external_upload" in parent or "契約" in name:
        return "uploaded_contract"
    if "ptq" in name:
        return "partner_quotation"
    if "pti" in name:
        return "partner_invoice"
    if "nke" in name:
        return "purchase_order"
    if "nkm" in name:
        return "quotation"
    if "nkk" in name:
        return "invoice"
    return "document"


def upsert_archive(
    db: Session,
    source_key: str,
    source: str,
    document_type: str,
    name: str,
    path_value: str | None,
    source_id: str | int | None = None,
    owner_name: str | None = None,
    partner_name: str | None = None,
    employee_name: str | None = None,
    target_month: str | None = None,
    status_value: str | None = None,
    amount: int | None = None,
    created_at: datetime | None = None,
    hidden: bool = False,
    attributes: dict | None = None,
) -> DocumentArchive:
    row = db.scalar(select(DocumentArchive).where(DocumentArchive.source_key == source_key))
    if not row:
        row = DocumentArchive(source_key=source_key, source=source, document_type=document_type, name=name)
        if created_at:
            row.created_at = created_at
        db.add(row)
    normalized_path = storage_path(path_value)
    path = Path(normalized_path) if normalized_path else None
    row.source = source
    row.source_id = str(source_id) if source_id is not None else None
    row.document_type = document_type
    row.name = name
    row.storage_path = normalized_path
    row.directory_path = directory_for(normalized_path)
    row.owner_name = owner_name
    row.partner_name = partner_name
    row.employee_name = employee_name
    row.target_month = target_month
    row.status = status_value
    row.amount = amount
    row.missing = bool(path and not path.exists())
    if hidden:
        row.hidden = True
    row.attributes = {**(row.attributes or {}), **(attributes or {})}
    return row


def sync_document_archives(db: Session) -> None:
    known_paths: set[str] = set()

    for doc in db.scalars(select(ExternalDocument).order_by(ExternalDocument.created_at.desc())).all():
        key = f"external_document:{doc.id}"
        if not doc.file_path:
            continue
        known_paths.add(str(Path(doc.file_path)))
        attrs = doc.attributes or {}
        original_name = attrs.get("original_filename") or file_name(doc.file_path)
        archive = upsert_archive(
            db,
            source_key=key,
            source="外部契約/準委任",
            source_id=doc.id,
            document_type=doc.document_type,
            name=f"{doc.document_no} / {original_name}",
            path_value=doc.file_path,
            owner_name=doc.partner.company_name if doc.partner else None,
            partner_name=doc.partner.company_name if doc.partner else None,
            target_month=doc.target_month,
            status_value=attrs.get("approval_status"),
            amount=doc.total,
            created_at=doc.created_at,
            hidden=document_deleted(doc) or key in hidden_keys(doc),
            attributes={"source_table": "external_documents"},
        )
        if document_deleted(doc):
            archive.hidden = True

    for reimbursement in db.scalars(select(Reimbursement).order_by(Reimbursement.created_at.desc())).all():
        for index, item in enumerate(reimbursement.invoice_file_paths or []):
            key = f"reimbursement:{reimbursement.id}:{index}"
            path_value = item.get("path") if isinstance(item, dict) else str(item)
            if path_value:
                known_paths.add(str(Path(path_value)))
            name = item.get("name") if isinstance(item, dict) else file_name(str(item))
            upsert_archive(
                db,
                source_key=key,
                source="経費精算",
                source_id=f"{reimbursement.id}:{index}",
                document_type="reimbursement",
                name=name or f"経費精算-{reimbursement.id}-{index + 1}",
                path_value=path_value,
                owner_name=reimbursement.employee.full_name if reimbursement.employee else None,
                employee_name=reimbursement.employee.full_name if reimbursement.employee else None,
                target_month=reimbursement.pay_month,
                status_value=reimbursement.status,
                amount=reimbursement.amount,
                created_at=reimbursement.created_at,
                hidden=key in hidden_keys(reimbursement),
                attributes={"source_table": "reimbursements"},
            )

    for item in db.scalars(select(PartnerOnboardingItem).order_by(PartnerOnboardingItem.created_at.desc())).all():
        key = f"onboarding:{item.id}"
        if not item.file_path:
            continue
        known_paths.add(str(Path(item.file_path)))
        partner_name = item.partner.company_name if item.partner else None
        upsert_archive(
            db,
            source_key=key,
            source="会社通知",
            source_id=item.id,
            document_type=item.item_code,
            name=item.original_filename or file_name(item.file_path),
            path_value=item.file_path,
            owner_name=partner_name,
            partner_name=partner_name,
            status_value=item.status,
            created_at=item.created_at,
            hidden=key in hidden_keys(item),
            attributes={"source_table": "partner_onboarding_items"},
        )

    for person in db.scalars(select(ExternalPersonnel).order_by(ExternalPersonnel.created_at.desc())).all():
        for kind, label, path_value in [
            ("resume", "履歴書", person.resume_path),
            ("avatar", "顔写真", person.avatar_path),
            ("timesheet", "勤務表", person.timesheet_path),
        ]:
            key = f"external_personnel:{person.id}:{kind}"
            if not path_value:
                continue
            known_paths.add(str(Path(path_value)))
            partner_name = person.partner.company_name if person.partner else person.company_name
            upsert_archive(
                db,
                source_key=key,
                source="外部人員",
                source_id=f"{person.id}:{kind}",
                document_type=kind,
                name=f"{person.full_name} / {label} / {file_name(path_value)}",
                path_value=path_value,
                owner_name=person.full_name,
                partner_name=partner_name,
                employee_name=person.full_name,
                target_month=person.assignment_month,
                status_value=person.status,
                created_at=person.created_at,
                hidden=key in hidden_keys(person),
                attributes={"source_table": "external_personnel"},
            )

    if STORAGE_ROOT.exists():
        for directory in SCAN_DIRECTORIES:
            scan_root = STORAGE_ROOT / directory
            if not scan_root.exists():
                continue
            for path in scan_root.rglob("*"):
                if not path.is_file():
                    continue
                normalized = str(path)
                if normalized in known_paths:
                    continue
                try:
                    relative = path.relative_to(STORAGE_ROOT).as_posix()
                except ValueError:
                    relative = path.name
                source_key = f"storage_scan:{hashlib.sha1(relative.encode('utf-8')).hexdigest()}"
                upsert_archive(
                    db,
                    source_key=source_key,
                    source="履歴ファイル",
                    source_id=source_key.split(":", 1)[1],
                    document_type=guess_document_type(path),
                    name=path.name,
                    path_value=normalized,
                    created_at=datetime.fromtimestamp(path.stat().st_mtime),
                    attributes={"source_table": "storage_scan", "relative_path": relative},
                )
    db.flush()


def document_item(
    key: str,
    source: str,
    document_type: str,
    name: str,
    download_url: str,
    owner_name: str | None = None,
    partner_name: str | None = None,
    employee_name: str | None = None,
    target_month: str | None = None,
    status_value: str | None = None,
    amount: int | None = None,
    created_at: datetime | None = None,
) -> dict:
    return {
        "key": key,
        "source": source,
        "document_type": document_type,
        "name": name,
        "owner_name": owner_name,
        "partner_name": partner_name,
        "employee_name": employee_name,
        "target_month": target_month,
        "status": status_value,
        "amount": amount,
        "download_url": download_url,
        "created_at": created_at,
    }


def archive_item(row: DocumentArchive) -> dict:
    return {
        "key": row.source_key,
        "archive_id": row.id,
        "source": row.source,
        "document_type": row.document_type,
        "name": row.name,
        "owner_name": row.owner_name,
        "partner_name": row.partner_name,
        "employee_name": row.employee_name,
        "target_month": row.target_month,
        "status": row.status,
        "amount": row.amount,
        "directory_path": row.directory_path,
        "download_url": archive_download_url(row.id),
        "created_at": row.created_at,
    }


@router.get("")
def list_managed_documents(
    q: str | None = None,
    document_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    sync_document_archives(db)
    db.commit()
    stmt = select(DocumentArchive).where(DocumentArchive.hidden == False, DocumentArchive.missing == False).order_by(DocumentArchive.created_at.desc())  # noqa: E712
    if document_type:
        stmt = stmt.where(DocumentArchive.document_type == document_type)
    rows = [archive_item(row) for row in db.scalars(stmt).all()]
    if document_type:
        rows = [row for row in rows if row["document_type"] == document_type]
    if q:
        text = q.lower()
        rows = [
            row for row in rows
            if any(str(row.get(field) or "").lower().find(text) >= 0 for field in ["source", "document_type", "name", "owner_name", "partner_name", "employee_name", "target_month", "status"])
        ]
    rows.sort(key=lambda row: row.get("created_at") or datetime.min, reverse=True)
    return rows


@router.get("/archive/{archive_id}/download")
def download_archive_document(
    archive_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    row = db.get(DocumentArchive, archive_id)
    if not row or row.hidden or not row.storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    path = Path(row.storage_path)
    if not path.exists() or not path.is_file():
        row.missing = True
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    return FileResponse(path, filename=path.name)


@router.delete("/items")
def hide_managed_document(
    key: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    parts = key.split(":")
    if len(parts) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid document key")
    archive = db.scalar(select(DocumentArchive).where(DocumentArchive.source_key == key))
    if archive:
        archive.hidden = True
    source = parts[0]
    if source == "external_document" and len(parts) == 2:
        row = db.get(ExternalDocument, int(parts[1]))
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
        attrs = dict(row.attributes or {})
        attrs["deleted"] = True
        row.attributes = attrs
    elif source == "reimbursement" and len(parts) == 3:
        row = db.get(Reimbursement, int(parts[1]))
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
        add_hidden_key(row, key)
    elif source == "onboarding" and len(parts) == 2:
        row = db.get(PartnerOnboardingItem, int(parts[1]))
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
        add_hidden_key(row, key)
    elif source == "external_personnel" and len(parts) == 3:
        row = db.get(ExternalPersonnel, int(parts[1]))
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
        add_hidden_key(row, key)
    elif source == "storage_scan":
        pass
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid document key")
    db.commit()
    return {"ok": True}
