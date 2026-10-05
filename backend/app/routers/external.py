from __future__ import annotations

import io
import shutil
import secrets
import zipfile
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import ensure_role
from app.core.security import get_password_hash
from app.db import get_db
from app.deps import get_current_user
from app.models import BusinessPartner, ExternalContract, ExternalDocument, MonthlySettlement, SalaryRecord, User
from app.schemas import (
    BusinessPartnerCreate,
    BusinessPartnerOut,
    BusinessPartnerUpdate,
    ExternalContractCreate,
    ExternalContractOut,
    ExternalContractUpdate,
    ExternalDocumentGenerateIn,
    ExternalDocumentOut,
    ExternalDocumentSettlementUpdate,
    MonthlySettlementOut,
)
from app.services.external_documents import (
    FIXED_NIT_FILES,
    UPLOAD_DIR,
    create_document_file,
    document_no,
    ensure_storage_dirs,
    fixed_file_path,
    normalize_items,
    public_document_url,
    safe_filename,
)
from app.services.accounts import ensure_partner_user
from app.services.mail import send_mail

router = APIRouter(prefix="/external", tags=["external_contracts"])


def ensure_external_user(user: User) -> None:
    ensure_role(user, {"admin", "soumu", "pm"})


def partner_contract_end_date(partner: BusinessPartner) -> date | None:
    value = (partner.attributes or {}).get("contract_end_date")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def partner_terminated(partner: BusinessPartner) -> bool:
    return bool((partner.attributes or {}).get("terminated"))


def partner_contract_active(partner: BusinessPartner) -> bool:
    end_date = partner_contract_end_date(partner)
    return partner.status == "active" and not partner_terminated(partner) and (end_date is None or end_date >= date.today())


def active_partner_duplicate_detail(partner: BusinessPartner) -> str:
    end_date = partner_contract_end_date(partner)
    end_text = end_date.isoformat() if end_date else "未設定"
    return (
        f"{partner.company_name} は有効な契約がすでに存在します。"
        f"契約終了日: {end_text}。"
        "解約済み、または契約終了日を過ぎてから再締結してください。"
    )


def partner_company_kana(partner: BusinessPartner) -> str | None:
    return (partner.attributes or {}).get("company_kana")


def partner_login_id(partner: BusinessPartner) -> str | None:
    for account in partner.partner_users or []:
        if account.role == "partner" and account.is_active:
            return account.login_id
    return None


def set_partner_contract_flags(
    partner: BusinessPartner,
    contract_end_date: date | None | object = None,
    terminated: bool | None = None,
    clear_end_date: bool = False,
) -> None:
    attrs = dict(partner.attributes or {})
    if clear_end_date:
        attrs.pop("contract_end_date", None)
    elif isinstance(contract_end_date, date):
        attrs["contract_end_date"] = contract_end_date.isoformat()
    elif contract_end_date is None and "contract_end_date" in attrs:
        attrs.pop("contract_end_date", None)
    if terminated is not None:
        attrs["terminated"] = bool(terminated)
    partner.attributes = attrs or None


def apply_partner_payload(partner: BusinessPartner, payload: BusinessPartnerCreate | BusinessPartnerUpdate, partial: bool = False) -> None:
    updates = payload.model_dump(exclude_unset=partial)
    company_kana = updates.pop("company_kana", None)
    contract_end_date = updates.pop("contract_end_date", None)
    terminated = updates.pop("terminated", None)
    incoming_attrs = updates.pop("attributes", None)
    if incoming_attrs is not None:
        attrs = dict(partner.attributes or {})
        attrs.update(incoming_attrs)
        partner.attributes = attrs or None
    for key, value in updates.items():
        setattr(partner, key, value)
    if "company_kana" in payload.model_fields_set or not partial:
        attrs = dict(partner.attributes or {})
        if company_kana:
            attrs["company_kana"] = company_kana
        else:
            attrs.pop("company_kana", None)
        partner.attributes = attrs or None
    if "contract_end_date" in payload.model_fields_set or not partial:
        set_partner_contract_flags(partner, contract_end_date=contract_end_date, terminated=None)
    if "terminated" in payload.model_fields_set or not partial:
        set_partner_contract_flags(partner, contract_end_date=object(), terminated=bool(terminated))


def ensure_partner_can_recontract(partner: BusinessPartner) -> None:
    if partner_contract_active(partner):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=active_partner_duplicate_detail(partner),
        )
    if partner_contract_active(partner):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该公司契约仍在生效期间，不能重复新缔结契约。请先在已缔结公司设置契约结束时间或已经解约。",
        )


def maybe_create_partner_account(db: Session, partner: BusinessPartner, direction: str, successful: bool) -> tuple[str | None, str | None]:
    if not successful or direction not in {"downstream", "both"}:
        return None, None
    account, temporary_password = ensure_partner_user(db, partner, must_reset_password=True)
    return account.login_id, temporary_password


def ensure_partner_email_for_direction(direction: str | None, email: str | None) -> None:
    if direction in {"downstream", "both"} and not (email or "").strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="協力会社、または上流・協力会社には担当者メールが必須です。")


def partner_out(partner: BusinessPartner) -> dict:
    return {
        "id": partner.id,
        "company_name": partner.company_name,
        "company_kana": partner_company_kana(partner),
        "partner_type": partner.partner_type,
        "contracted_at": partner.contracted_at,
        "contract_end_date": partner_contract_end_date(partner),
        "terminated": partner_terminated(partner),
        "contract_active": partner_contract_active(partner),
        "partner_login_id": partner_login_id(partner),
        "status": partner.status,
        "contact_name": partner.contact_name,
        "email": partner.email,
        "phone": partner.phone,
        "address": partner.address,
        "bank_info": partner.bank_info,
        "note": partner.note,
        "attributes": partner.attributes,
        "created_at": partner.created_at,
        "updated_at": partner.updated_at,
    }


def contract_fixed_links(contract: ExternalContract) -> list[dict]:
    if contract.file_paths:
        return [
            {
                "id": f"file-{index + 1}",
                "name": Path(path).name,
                "download_url": f"/api/external/contracts/{contract.id}/files/{index}/download",
            }
            for index, path in enumerate(contract.file_paths or [])
        ]
    # NIT-1..5 are still available through public token links, but are not shown in the internal contract table.
    return []


def fixed_files_zip_response(filename: str = "nit-fixed-files.zip") -> StreamingResponse:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in FIXED_NIT_FILES:
            path = fixed_file_path(item["id"])
            if path:
                archive.write(path, arcname=path.name)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def contract_out(contract: ExternalContract) -> dict:
    return {
        "id": contract.id,
        "partner_id": contract.partner_id,
        "partner_name": contract.partner.company_name if contract.partner else None,
        "contracted_success": contract.status == "signed",
        "partner_login_id": partner_login_id(contract.partner) if contract.partner else None,
        "partner_temporary_password": getattr(contract, "_partner_temporary_password", None),
        "direction": contract.direction,
        "title": contract.title,
        "contract_type": contract.contract_type,
        "status": contract.status,
        "contracted_at": contract.contracted_at,
        "download_token": contract.download_token,
        "file_paths": contract.file_paths,
        "fixed_file_links": contract_fixed_links(contract),
        "note": contract.note,
        "attributes": contract.attributes,
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
    }


def document_settlement(document: ExternalDocument) -> dict:
    attrs = document.attributes or {}
    settlement = attrs.get("settlement") or {}
    actual_amount = settlement.get("actual_amount")
    return {
        "confirmed": bool(settlement.get("confirmed", True)),
        "actual_amount": int(actual_amount if actual_amount is not None else document.total or 0),
    }


def document_out(document: ExternalDocument) -> dict:
    settlement = document_settlement(document)
    return {
        "id": document.id,
        "partner_id": document.partner_id,
        "partner_name": document.partner.company_name if document.partner else None,
        "external_contract_id": document.external_contract_id,
        "source_document_id": document.source_document_id,
        "document_type": document.document_type,
        "direction": document.direction,
        "document_no": document.document_no,
        "target_month": document.target_month,
        "issue_date": document.issue_date,
        "due_date": document.due_date,
        "subtotal": document.subtotal,
        "tax": document.tax,
        "total": document.total,
        "items": document.items,
        "file_path": document.file_path,
        "note": document.note,
        "attributes": document.attributes,
        "settlement_confirmed": settlement["confirmed"],
        "settlement_actual_amount": settlement["actual_amount"],
        "download_url": public_document_url(document.id) if document.file_path else None,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def settlement_document_row(document: ExternalDocument) -> dict:
    settlement = document_settlement(document)
    effective_amount = settlement["actual_amount"] if settlement["confirmed"] else 0
    return {
        "id": document.id,
        "document_type": document.document_type,
        "document_no": document.document_no,
        "partner_name": document.partner.company_name if document.partner else None,
        "target_month": document.target_month,
        "issue_date": document.issue_date.isoformat() if document.issue_date else None,
        "total": int(document.total or 0),
        "settlement_confirmed": settlement["confirmed"],
        "settlement_actual_amount": settlement["actual_amount"],
        "effective_amount": int(effective_amount),
        "download_url": public_document_url(document.id) if document.file_path else None,
    }


def document_deleted(document: ExternalDocument) -> bool:
    return bool((document.attributes or {}).get("deleted"))


def direction_slots(direction: str) -> set[str]:
    if direction == "both":
        return {"upstream", "downstream"}
    return {direction}


def ensure_contract_slot_available(
    db: Session,
    partner_id: int,
    direction: str,
    effective: bool,
    exclude_contract_id: int | None = None,
) -> None:
    if not effective:
        return
    desired_slots = direction_slots(direction)
    rows = db.scalars(select(ExternalContract).where(ExternalContract.partner_id == partner_id)).all()
    for row in rows:
        if exclude_contract_id and row.id == exclude_contract_id:
            continue
        if row.status != "signed":
            continue
        if desired_slots & direction_slots(row.direction):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该公司当前方向存在生效中的契约，请先标记到期后再新增。",
            )


def next_month_end(value: date) -> date:
    month = value.month + 1
    year = value.year
    if month == 13:
        month = 1
        year += 1
    if month == 12:
        following = date(year + 1, 1, 1)
    else:
        following = date(year, month + 1, 1)
    return following - timedelta(days=1)


def get_partner_or_404(db: Session, partner_id: int) -> BusinessPartner:
    partner = db.get(BusinessPartner, partner_id)
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="已缔结公司不存在")
    return partner


def ensure_partner_direction(partner: BusinessPartner, allowed: set[str], action_name: str) -> None:
    partner_type = partner.partner_type or ""
    if partner_type == "both" or partner_type in allowed:
        return
    allowed_text = "/".join(sorted(allowed | {"both"}))
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"{action_name} 只能用于 {allowed_text} 类型公司",
    )


def merge_partner_type(current: str | None, direction: str) -> str:
    if not current or current == direction:
        return direction
    if current == "both":
        return "both"
    return "both"


def make_document(
    db: Session,
    payload: ExternalDocumentGenerateIn,
    doc_type: str,
    direction: str,
    prefix: str,
    user: User,
    source_document_id: int | None = None,
) -> ExternalDocument:
    partner = get_partner_or_404(db, payload.partner_id)
    raw_items = [item.model_dump() if hasattr(item, "model_dump") else item for item in payload.items]
    items, subtotal, tax, total = normalize_items(raw_items)
    doc = ExternalDocument(
        partner_id=payload.partner_id,
        external_contract_id=payload.external_contract_id,
        source_document_id=source_document_id if source_document_id is not None else payload.source_document_id,
        document_type=doc_type,
        direction=direction,
        document_no=payload.document_no or document_no(prefix),
        target_month=payload.target_month,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        subtotal=subtotal,
        tax=tax,
        total=total,
        items=items,
        note=payload.note,
        attributes=payload.attributes,
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    path = create_document_file(partner, doc)
    doc.file_path = str(path)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/public/contracts/{token}/fixed-files")
def public_fixed_files(token: str, db: Session = Depends(get_db)):
    contract = db.scalar(select(ExternalContract).where(ExternalContract.download_token == token))
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="下载链接不存在")
    return contract_fixed_links(contract)


@router.get("/public/contracts/{token}/fixed-files/{file_id}")
def public_download_fixed_file(token: str, file_id: str, db: Session = Depends(get_db)):
    contract = db.scalar(select(ExternalContract).where(ExternalContract.download_token == token))
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="下载链接不存在")
    if file_id == "download-all":
        return fixed_files_zip_response(f"nit-fixed-files-{contract.id}.zip")
    path = fixed_file_path(file_id)
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="固定文件不存在")
    return FileResponse(path, filename=path.name)


@router.get("/public/contracts/{token}/fixed-files/download-all")
def public_download_fixed_files_zip(token: str, db: Session = Depends(get_db)):
    contract = db.scalar(select(ExternalContract).where(ExternalContract.download_token == token))
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="下载链接不存在")
    return fixed_files_zip_response(f"nit-fixed-files-{contract.id}.zip")


@router.get("/partners", response_model=list[BusinessPartnerOut])
def list_partners(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    rows = db.scalars(
        select(BusinessPartner)
        .where(BusinessPartner.status == "active")
        .order_by(BusinessPartner.company_name)
    ).all()
    return [partner_out(row) for row in rows]


@router.post("/partners", response_model=BusinessPartnerOut)
def create_partner(payload: BusinessPartnerCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    ensure_partner_email_for_direction(payload.partner_type, str(payload.email) if payload.email else None)
    partner = db.scalar(select(BusinessPartner).where(BusinessPartner.company_name == payload.company_name))
    if partner and partner_contract_active(partner):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=active_partner_duplicate_detail(partner))
    if not partner:
        partner = BusinessPartner()
    else:
        attrs = dict(partner.attributes or {})
        attrs.pop("deleted", None)
        partner.attributes = attrs or None
    apply_partner_payload(partner, payload)
    partner.status = payload.status or "active"
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner_out(partner)
    if db.scalar(select(BusinessPartner).where(BusinessPartner.company_name == payload.company_name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="公司名已存在")
    partner = BusinessPartner()
    apply_partner_payload(partner, payload)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner_out(partner)


@router.put("/partners/{partner_id}", response_model=BusinessPartnerOut)
def update_partner(partner_id: int, payload: BusinessPartnerUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    partner = get_partner_or_404(db, partner_id)
    if payload.company_name and payload.company_name != partner.company_name:
        existing = db.scalar(select(BusinessPartner).where(BusinessPartner.company_name == payload.company_name))
        if existing and existing.id != partner.id:
            if partner_contract_active(existing):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=active_partner_duplicate_detail(existing))
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同名の会社レコードが存在します。既存レコードを確認してください。")
    apply_partner_payload(partner, payload, partial=True)
    ensure_partner_email_for_direction(partner.partner_type, partner.email)
    db.commit()
    db.refresh(partner)
    return partner_out(partner)


@router.delete("/partners/{partner_id}")
def delete_partner(partner_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    partner = get_partner_or_404(db, partner_id)
    attrs = dict(partner.attributes or {})
    attrs["deleted"] = True
    partner.attributes = attrs
    partner.status = "deleted"
    db.commit()
    return {"ok": True}


@router.post("/partners/{partner_id}/send-account-mail")
def send_partner_account_mail(partner_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    partner = get_partner_or_404(db, partner_id)
    if partner.partner_type not in {"downstream", "both"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="partner account mail is only available for downstream/both partners")
    if not partner.email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="partner email is required")
    account, temporary_password = ensure_partner_user(db, partner, must_reset_password=True)
    if not temporary_password:
        temporary_password = secrets.token_urlsafe(12)
        account.password_hash = get_password_hash(temporary_password)
        account.must_reset_password = True
        account.is_active = True
    subject = "NIT OA System アカウント情報"
    body = (
        f"{partner.company_name} ご担当者様\n\n"
        "NIT OA System のパートナーアカウントを発行しました。\n"
        "以下の情報でログインし、初回ログイン時にパスワードを変更してください。\n\n"
        f"ログインURL: {get_settings().frontend_url}\n"
        f"ログインID: {account.login_id}\n"
        f"一時パスワード: {temporary_password}\n\n"
        "本メールにお心当たりがない場合は、NIT 担当者までご連絡ください。\n"
    )
    try:
        sent = send_mail(partner.email, subject, body)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"mail send failed: {exc}") from exc
    if not sent:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP is not configured")
    db.commit()
    return {"ok": True, "email": partner.email, "partner_login_id": account.login_id}


@router.get("/contracts", response_model=list[ExternalContractOut])
def list_external_contracts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    rows = db.scalars(select(ExternalContract).order_by(ExternalContract.created_at.desc())).all()
    return [contract_out(row) for row in rows]


@router.post("/contracts", response_model=ExternalContractOut)
def create_external_contract(payload: ExternalContractCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    company_name = payload.company_name.strip()
    successful = payload.contracted_success or payload.status == "signed"
    partner = db.scalar(select(BusinessPartner).where(BusinessPartner.company_name == company_name))
    if partner:
        ensure_partner_can_recontract(partner)
        attrs = dict(partner.attributes or {})
        attrs.pop("deleted", None)
        partner.attributes = attrs or None
        partner.partner_type = payload.direction
        partner.status = "active" if successful else "pending"
    else:
        partner = BusinessPartner(
            company_name=company_name,
            partner_type=payload.direction,
            status="active" if successful else "pending",
        )
        db.add(partner)
        db.flush()
    if payload.contact_name is not None:
        partner.contact_name = payload.contact_name
    if payload.email is not None:
        partner.email = str(payload.email)
    if payload.phone is not None:
        partner.phone = payload.phone
    ensure_partner_email_for_direction(payload.direction, partner.email)
    if successful:
        partner.status = "active"
        partner.contracted_at = payload.contracted_at or partner.contracted_at or date.today()
        set_partner_contract_flags(partner, terminated=False, clear_end_date=True)
    account_login_id, temporary_password = maybe_create_partner_account(db, partner, payload.direction, successful)
    contract = ExternalContract(
        partner_id=partner.id,
        direction=payload.direction,
        title=payload.title,
        contract_type=payload.contract_type,
        status="signed" if successful else payload.status,
        contracted_at=(payload.contracted_at or date.today()) if successful else None,
        note=payload.note,
        attributes=payload.attributes,
        download_token=secrets.token_urlsafe(24) if payload.direction in {"downstream", "both"} else None,
        file_paths=[],
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    contract._partner_temporary_password = temporary_password
    return contract_out(contract)


@router.put("/contracts/{contract_id}", response_model=ExternalContractOut)
def update_external_contract(contract_id: int, payload: ExternalContractUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    contract = db.get(ExternalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="外部契约不存在")
    updates = payload.model_dump(exclude_unset=True)
    contracted_success = updates.pop("contracted_success", None)
    contact_name = updates.pop("contact_name", None)
    email = updates.pop("email", None)
    phone = updates.pop("phone", None)
    temporary_password = None
    for key, value in updates.items():
        setattr(contract, key, value)
    if contract.partner and payload.direction:
        contract.partner.partner_type = payload.direction
    if contract.partner:
        if contact_name is not None:
            contract.partner.contact_name = contact_name
        if email is not None:
            contract.partner.email = str(email)
        if phone is not None:
            contract.partner.phone = phone
        ensure_partner_email_for_direction(contract.partner.partner_type, contract.partner.email)
    if contracted_success is not None and contract.partner:
        contract.partner.status = "active" if contracted_success else "pending"
        if contracted_success:
            contract.status = "signed"
            contract.contracted_at = contract.contracted_at or date.today()
            contract.partner.contracted_at = contract.contracted_at
            set_partner_contract_flags(contract.partner, terminated=False, clear_end_date=True)
            _, temporary_password = maybe_create_partner_account(db, contract.partner, contract.direction, True)
        else:
            contract.status = "draft"
            contract.contracted_at = None
    if contracted_success is None and contract.status == "signed" and contract.partner:
        contract.partner.status = "active"
        contract.contracted_at = contract.contracted_at or date.today()
        contract.partner.contracted_at = contract.contracted_at
        set_partner_contract_flags(contract.partner, terminated=False, clear_end_date=True)
        _, temporary_password = maybe_create_partner_account(db, contract.partner, contract.direction, True)
    if contract.direction in {"downstream", "both"} and not contract.download_token:
        contract.download_token = secrets.token_urlsafe(24)
    db.commit()
    db.refresh(contract)
    contract._partner_temporary_password = temporary_password
    return contract_out(contract)


@router.delete("/contracts/{contract_id}")
def delete_external_contract(contract_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    contract = db.get(ExternalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="外部契约不存在")
    for document in list(contract.documents or []):
        document.external_contract_id = None
    db.delete(contract)
    db.commit()
    return {"ok": True}


@router.get("/contracts/{contract_id}/files/{file_index}/download")
def download_contract_file(contract_id: int, file_index: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    contract = db.get(ExternalContract, contract_id)
    if not contract or not contract.file_paths or file_index < 0 or file_index >= len(contract.file_paths):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    path = Path(contract.file_paths[file_index])
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    return FileResponse(path, filename=path.name)


@router.post("/contracts/upload", response_model=ExternalContractOut)
def upload_external_contract(
    partner_id: int | None = Form(None),
    company_name: str | None = Form(None),
    direction: str = Form("upstream"),
    title: str = Form("上家契約書"),
    contracted_at: date | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_external_user(user)
    temporary_password = None
    if direction not in {"upstream", "downstream", "both"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="契约方向必须为 upstream/downstream")
    if partner_id:
        partner = get_partner_or_404(db, partner_id)
        ensure_partner_can_recontract(partner)
        attrs = dict(partner.attributes or {})
        attrs.pop("deleted", None)
        partner.attributes = attrs or None
        partner.partner_type = direction
        partner.status = "active"
        partner.contracted_at = contracted_at or date.today()
        set_partner_contract_flags(partner, terminated=False, clear_end_date=True)
        _, temporary_password = maybe_create_partner_account(db, partner, direction, True)
    else:
        name = (company_name or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="company_name is required")
        partner = db.scalar(select(BusinessPartner).where(BusinessPartner.company_name == name))
        if partner:
            ensure_partner_can_recontract(partner)
            attrs = dict(partner.attributes or {})
            attrs.pop("deleted", None)
            partner.attributes = attrs or None
            partner.partner_type = direction
            partner.status = "active"
            partner.contracted_at = contracted_at or date.today()
            set_partner_contract_flags(partner, terminated=False, clear_end_date=True)
            _, temporary_password = maybe_create_partner_account(db, partner, direction, True)
        else:
            partner = BusinessPartner(
                company_name=name,
                partner_type=direction,
                status="active",
                contracted_at=contracted_at or date.today(),
            )
            db.add(partner)
            db.flush()
            _, temporary_password = maybe_create_partner_account(db, partner, direction, True)
    ensure_partner_email_for_direction(direction, partner.email)
    ensure_storage_dirs()
    file_paths: list[str] = []
    for file in files:
        filename = safe_filename(f"{date.today().isoformat()}_{partner.company_name}_{file.filename}")
        path = UPLOAD_DIR / filename
        with path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_paths.append(str(path))
    contract = ExternalContract(
        partner_id=partner.id,
        direction=direction,
        title=title,
        contract_type="uploaded",
        status="signed",
        contracted_at=contracted_at or date.today(),
        file_paths=file_paths,
        download_token=secrets.token_urlsafe(24) if direction in {"downstream", "both"} else None,
    )
    db.add(contract)
    db.flush()
    issue_date = contracted_at or date.today()
    for path in file_paths:
        doc = ExternalDocument(
            partner_id=partner.id,
            external_contract_id=contract.id,
            document_type="uploaded_contract",
            direction=direction,
            document_no=document_no("UPL"),
            target_month=issue_date.strftime("%Y-%m"),
            issue_date=issue_date,
            subtotal=0,
            tax=0,
            total=0,
            file_path=path,
            created_by=user.id,
            items=[],
        )
        db.add(doc)
    db.commit()
    db.refresh(contract)
    contract._partner_temporary_password = temporary_password
    return contract_out(contract)


@router.get("/fixed-files")
def list_fixed_files(user: User = Depends(get_current_user)):
    ensure_external_user(user)
    return [
        {**item, "download_url": f"/api/external/fixed-files/{item['id']}/download"}
        for item in FIXED_NIT_FILES
    ]


@router.get("/fixed-files/download-all")
def download_fixed_files_zip(user: User = Depends(get_current_user)):
    ensure_external_user(user)
    return fixed_files_zip_response()


@router.get("/fixed-files/{file_id}/download")
def download_fixed_file(file_id: str, user: User = Depends(get_current_user)):
    ensure_external_user(user)
    path = fixed_file_path(file_id)
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="固定文件不存在")
    return FileResponse(path, filename=path.name)


@router.get("/documents", response_model=list[ExternalDocumentOut])
def list_documents(
    target_month: str | None = None,
    document_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_external_user(user)
    stmt = select(ExternalDocument).order_by(ExternalDocument.created_at.desc())
    if target_month:
        stmt = stmt.where(ExternalDocument.target_month == target_month)
    if document_type:
        stmt = stmt.where(ExternalDocument.document_type == document_type)
    return [document_out(row) for row in db.scalars(stmt).all() if not document_deleted(row)]


@router.get("/partner-quotations/approved", response_model=list[ExternalDocumentOut])
def list_approved_partner_quotations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    rows = db.scalars(
        select(ExternalDocument)
        .where(ExternalDocument.document_type == "partner_quotation")
        .order_by(ExternalDocument.created_at.desc())
    ).all()
    return [
        document_out(row)
        for row in rows
        if not document_deleted(row) and (row.attributes or {}).get("approval_status") == "approved"
    ]


@router.get("/documents/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    document = db.get(ExternalDocument, document_id)
    if not document or document_deleted(document) or not document.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="书类文件不存在")
    path = Path(document.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")
    return FileResponse(path, filename=path.name)


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    document = db.get(ExternalDocument, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    attrs = dict(document.attributes or {})
    attrs["deleted"] = True
    document.attributes = attrs
    db.commit()
    return {"ok": True}


@router.put("/documents/{document_id}/settlement", response_model=ExternalDocumentOut)
def update_document_settlement(
    document_id: int,
    payload: ExternalDocumentSettlementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin"})
    document = db.get(ExternalDocument, document_id)
    if not document or document_deleted(document) or document.document_type not in {"invoice", "purchase_order", "partner_invoice"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    attrs = dict(document.attributes or {})
    attrs["settlement"] = {
        "confirmed": payload.settlement_confirmed,
        "actual_amount": payload.settlement_actual_amount,
    }
    document.attributes = attrs
    db.commit()
    db.refresh(document)
    return document_out(document)


@router.post("/purchase-orders", response_model=ExternalDocumentOut)
def generate_purchase_order(payload: ExternalDocumentGenerateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    partner = get_partner_or_404(db, payload.partner_id)
    ensure_partner_direction(partner, {"downstream"}, "发注书")
    if not payload.source_document_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="purchase order requires an approved partner quotation")
    quotation = db.get(ExternalDocument, payload.source_document_id)
    if (
        not quotation
        or document_deleted(quotation)
        or quotation.partner_id != payload.partner_id
        or quotation.document_type != "partner_quotation"
        or (quotation.attributes or {}).get("approval_status") != "approved"
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="approved partner quotation is required")
    if not payload.items:
        payload = payload.model_copy(update={"items": quotation.items or []})
    document = make_document(db, payload, "purchase_order", "downstream", "NKE", user, source_document_id=quotation.id)
    return document_out(document)


@router.post("/quotations", response_model=ExternalDocumentOut)
def generate_quotation(payload: ExternalDocumentGenerateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    partner = get_partner_or_404(db, payload.partner_id)
    ensure_partner_direction(partner, {"upstream"}, "見積書")
    document = make_document(db, payload, "quotation", "upstream", "NKM", user)
    return document_out(document)


@router.post("/invoices/from-quotation/{quotation_id}", response_model=ExternalDocumentOut)
def generate_invoice_from_quotation(
    quotation_id: int,
    due_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_external_user(user)
    quotation = db.get(ExternalDocument, quotation_id)
    if not quotation or quotation.document_type != "quotation":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="見積書不存在")
    partner = get_partner_or_404(db, quotation.partner_id)
    ensure_partner_direction(partner, {"upstream"}, "请求书")
    invoice = ExternalDocument(
        partner_id=quotation.partner_id,
        external_contract_id=quotation.external_contract_id,
        source_document_id=quotation.id,
        document_type="invoice",
        direction="upstream",
        document_no=document_no("NKK"),
        target_month=quotation.target_month,
        issue_date=date.today(),
        due_date=due_date or next_month_end(date.today()),
        subtotal=quotation.subtotal,
        tax=quotation.tax,
        total=quotation.total,
        items=quotation.items,
        note=quotation.note,
        attributes={**(quotation.attributes or {}), "bank_info": partner.bank_info or {}},
        created_by=user.id,
    )
    db.add(invoice)
    db.flush()
    invoice.file_path = str(create_document_file(partner, invoice))
    db.commit()
    db.refresh(invoice)
    return document_out(invoice)


@router.post("/invoices", response_model=ExternalDocumentOut)
def generate_invoice(
    payload: ExternalDocumentGenerateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_external_user(user)
    partner = get_partner_or_404(db, payload.partner_id)
    ensure_partner_direction(partner, {"upstream"}, "請求書")
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="明細を1件以上入力してください")
    attributes = {
        **(payload.attributes or {}),
        "bank_info": partner.bank_info or {},
        "creation_mode": "manual",
    }
    document = make_document(
        db,
        payload.model_copy(update={"attributes": attributes}),
        "invoice",
        "upstream",
        "NKK",
        user,
    )
    return document_out(document)


@router.get("/settlements/{year_month}", response_model=MonthlySettlementOut)
def get_monthly_settlement(year_month: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_external_user(user)
    invoice_documents = [
        document for document in db.scalars(
        select(ExternalDocument).where(
            ExternalDocument.document_type == "invoice",
            ExternalDocument.target_month == year_month,
        )
    ).all() if not document_deleted(document)
    ]
    purchase_documents = [
        document for document in db.scalars(
        select(ExternalDocument).where(
            ExternalDocument.document_type == "partner_invoice",
            ExternalDocument.target_month == year_month,
        )
    ).all() if not document_deleted(document) and (document.attributes or {}).get("approval_status") == "approved"
    ]
    invoice_rows = [settlement_document_row(document) for document in invoice_documents]
    purchase_rows = [settlement_document_row(document) for document in purchase_documents]
    invoice_total = sum(row["effective_amount"] for row in invoice_rows)
    purchase_total = sum(row["effective_amount"] for row in purchase_rows)
    salary_rows = db.scalars(select(SalaryRecord).where(SalaryRecord.year_month == year_month)).all()
    salary_total = sum(row.actual_salary or 0 for row in salary_rows)
    settlement = db.scalar(select(MonthlySettlement).where(MonthlySettlement.year_month == year_month))
    detail = {
        "invoice_count": len(invoice_rows),
        "purchase_order_count": len(purchase_rows),
        "salary_count": len(salary_rows),
        "invoices": invoice_rows,
        "purchase_orders": purchase_rows,
    }
    if settlement and settlement.locked:
        return settlement
    if not settlement:
        settlement = MonthlySettlement(year_month=year_month)
        db.add(settlement)
    settlement.invoice_total = int(invoice_total)
    settlement.purchase_order_total = int(purchase_total)
    settlement.salary_total = int(salary_total)
    settlement.net_income = int(invoice_total) - int(purchase_total) - int(salary_total)
    settlement.detail = detail
    db.commit()
    db.refresh(settlement)
    return settlement
