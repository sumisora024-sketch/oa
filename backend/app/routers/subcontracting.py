import io
import io
import shutil
import zipfile
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import BusinessPartner, ExternalDocument, PartnerOnboardingItem, User, WorkflowRequest
from app.routers.external import document_deleted, document_out, ensure_partner_direction, get_partner_or_404
from app.schemas import (
    BusinessPartnerOut,
    ExternalDocumentOut,
    PartnerOnboardingFormIn,
    PartnerOnboardingItemOut,
    PartnerQuotationSubmitIn,
)
from app.services.external_documents import (
    FIXED_NIT_FILES,
    UPLOAD_DIR,
    create_document_file,
    document_no,
    ensure_storage_dirs,
    fixed_file_path,
    normalize_items,
    safe_filename,
)
from app.services.workflow import create_workflow_request

router = APIRouter(prefix="/subcontracting", tags=["subcontracting"])

ONBOARDING_FORM_ITEMS = {"nit-1", "nit-2", "nit-5"}
ONBOARDING_UPLOAD_ITEMS = {"nit-3", "nit-4"}
ONBOARDING_REQUIRED_FIELDS = [
    "company_name",
    "address",
    "representative_name",
    "contact_name",
    "email",
    "phone",
    "agreed_on",
]


def ensure_subcontracting_user(user: User) -> None:
    ensure_role(user, {"admin", "partner"})


def current_partner(db: Session, user: User, partner_id: int | None = None) -> BusinessPartner:
    if user.role == "partner":
        if not user.partner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="partner account is not linked")
        return get_partner_or_404(db, user.partner_id)
    if not partner_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="partner_id is required")
    return get_partner_or_404(db, partner_id)


def save_partner_document_upload(file: UploadFile, partner: BusinessPartner, prefix: str, marker: str) -> str:
    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="file is required")
    ensure_storage_dirs()
    filename = safe_filename(f"{marker}_{partner.company_name}_{document_no(prefix)}_{file.filename}")
    path = UPLOAD_DIR / filename
    with path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return str(path)


def get_onboarding_item(db: Session, partner_id: int, item_code: str) -> PartnerOnboardingItem | None:
    return db.scalar(
        select(PartnerOnboardingItem).where(
            PartnerOnboardingItem.partner_id == partner_id,
            PartnerOnboardingItem.item_code == item_code,
        )
    )


def onboarding_template(item_code: str) -> dict | None:
    return next((item for item in FIXED_NIT_FILES if item["id"] == item_code), None)


def onboarding_item_out(partner: BusinessPartner, item_code: str, row: PartnerOnboardingItem | None = None) -> dict:
    template = onboarding_template(item_code) or {"id": item_code, "name": item_code, "filename": None}
    return {
        "id": row.id if row else None,
        "partner_id": partner.id,
        "item_code": item_code,
        "name": template["name"],
        "filename": template.get("filename"),
        "template_download_url": f"/api/subcontracting/fixed-files/{item_code}/download",
        "upload_download_url": f"/api/subcontracting/onboarding/{item_code}/upload/download" if row and row.file_path else None,
        "status": row.status if row else "pending",
        "form_data": row.form_data if row else None,
        "original_filename": row.original_filename if row else None,
        "completed_at": row.completed_at if row else None,
        "updated_at": row.updated_at if row else None,
    }


def ensure_onboarding_item(db: Session, partner: BusinessPartner, item_code: str) -> PartnerOnboardingItem:
    if item_code not in ONBOARDING_FORM_ITEMS | ONBOARDING_UPLOAD_ITEMS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notice item not found")
    row = get_onboarding_item(db, partner.id, item_code)
    if row:
        return row
    row = PartnerOnboardingItem(partner_id=partner.id, item_code=item_code, status="pending")
    db.add(row)
    db.flush()
    return row


def onboarding_completed(db: Session, partner_id: int) -> bool:
    rows = db.scalars(select(PartnerOnboardingItem).where(PartnerOnboardingItem.partner_id == partner_id)).all()
    status_by_code = {row.item_code: row.status for row in rows}
    return all(status_by_code.get(item["id"]) == "completed" for item in FIXED_NIT_FILES)


def ensure_partner_onboarding_complete(db: Session, partner: BusinessPartner, user: User) -> None:
    if user.role != "partner":
        return
    if not onboarding_completed(db, partner.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="会社通知の確認と必要書類の提出を先に完了してください")


def validate_month_range(start_month: str, end_month: str) -> None:
    if end_month < start_month:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="対象終了月は対象開始月以降を指定してください")


def approved_partner_quotation(db: Session, partner_id: int, quotation_id: int) -> ExternalDocument:
    quotation = db.get(ExternalDocument, quotation_id)
    if (
        not quotation
        or document_deleted(quotation)
        or quotation.partner_id != partner_id
        or quotation.document_type != "partner_quotation"
        or (quotation.attributes or {}).get("approval_status") != "approved"
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="承認済みのパートナー見積書を選択してください")
    return quotation


def create_document_workflow(db: Session, doc: ExternalDocument, workflow_type: str, requester_id: int | None) -> WorkflowRequest:
    workflow = create_workflow_request(
        db,
        workflow_type=workflow_type,
        entity_type="external_document",
        entity_id=doc.id,
        title=f"{doc.partner.company_name if doc.partner else doc.partner_id} {doc.target_month} {workflow_type}",
        requester_id=requester_id,
        attributes={"partner_id": doc.partner_id, "document_no": doc.document_no, "target_month": doc.target_month},
        link="/approvals/contracts",
    )
    attrs = dict(doc.attributes or {})
    attrs["workflow_id"] = workflow.id
    doc.attributes = attrs
    return workflow


def fixed_files_zip_response(filename: str = "nit-company-notice-files.zip") -> StreamingResponse:
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


@router.get("/me", response_model=BusinessPartnerOut)
def my_partner(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_subcontracting_user(user)
    partner = current_partner(db, user, user.partner_id)
    from app.routers.external import partner_out

    return partner_out(partner)


@router.get("/quotations", response_model=list[ExternalDocumentOut])
def list_partner_quotations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_subcontracting_user(user)
    stmt = select(ExternalDocument).where(ExternalDocument.document_type == "partner_quotation").order_by(ExternalDocument.created_at.desc())
    if user.role == "partner":
        stmt = stmt.where(ExternalDocument.partner_id == user.partner_id)
    return [document_out(row) for row in db.scalars(stmt).all() if not document_deleted(row)]


@router.get("/invoices", response_model=list[ExternalDocumentOut])
def list_partner_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_subcontracting_user(user)
    stmt = select(ExternalDocument).where(ExternalDocument.document_type == "partner_invoice").order_by(ExternalDocument.created_at.desc())
    if user.role == "partner":
        stmt = stmt.where(ExternalDocument.partner_id == user.partner_id)
    return [document_out(row) for row in db.scalars(stmt).all() if not document_deleted(row)]


@router.get("/fixed-files")
def list_notice_fixed_files(user: User = Depends(get_current_user)):
    ensure_subcontracting_user(user)
    return [
        {**item, "download_url": f"/api/subcontracting/fixed-files/{item['id']}/download"}
        for item in FIXED_NIT_FILES
    ]


@router.get("/fixed-files/download-all")
def download_notice_fixed_files_zip(user: User = Depends(get_current_user)):
    ensure_subcontracting_user(user)
    return fixed_files_zip_response()


@router.get("/fixed-files/{file_id}/download")
def download_notice_fixed_file(file_id: str, user: User = Depends(get_current_user)):
    ensure_subcontracting_user(user)
    path = fixed_file_path(file_id)
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fixed file not found")
    return FileResponse(path, filename=Path(path).name)


@router.get("/onboarding", response_model=list[PartnerOnboardingItemOut])
def list_onboarding_items(
    partner_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_subcontracting_user(user)
    partner = current_partner(db, user, partner_id or user.partner_id)
    rows = {
        row.item_code: row
        for row in db.scalars(select(PartnerOnboardingItem).where(PartnerOnboardingItem.partner_id == partner.id)).all()
    }
    return [onboarding_item_out(partner, item["id"], rows.get(item["id"])) for item in FIXED_NIT_FILES]


@router.post("/onboarding/{item_code}/form", response_model=PartnerOnboardingItemOut)
def complete_onboarding_form(
    item_code: str,
    payload: PartnerOnboardingFormIn,
    partner_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_subcontracting_user(user)
    if item_code not in ONBOARDING_FORM_ITEMS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="この書類はアップロードで提出してください")
    partner = current_partner(db, user, partner_id or user.partner_id)
    form_data = payload.form_data or {}
    missing = [field for field in ONBOARDING_REQUIRED_FIELDS if not str(form_data.get(field) or "").strip()]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"必須項目が未入力です: {', '.join(missing)}")
    if not form_data.get("scrolled_to_bottom"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="書類の最後まで確認してください")
    row = ensure_onboarding_item(db, partner, item_code)
    row.status = "completed"
    row.form_data = form_data
    row.completed_at = datetime.utcnow()
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return onboarding_item_out(partner, item_code, row)


@router.post("/onboarding/{item_code}/upload", response_model=PartnerOnboardingItemOut)
def upload_onboarding_file(
    item_code: str,
    partner_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_subcontracting_user(user)
    if item_code not in ONBOARDING_UPLOAD_ITEMS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="この書類はフォーム入力で完了してください")
    partner = current_partner(db, user, partner_id or user.partner_id)
    path = save_partner_document_upload(file, partner, "NIT", item_code)
    row = ensure_onboarding_item(db, partner, item_code)
    row.status = "completed"
    row.file_path = path
    row.original_filename = file.filename
    row.completed_at = datetime.utcnow()
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return onboarding_item_out(partner, item_code, row)


@router.get("/onboarding/{item_code}/upload/download")
def download_onboarding_upload(
    item_code: str,
    partner_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_subcontracting_user(user)
    partner = current_partner(db, user, partner_id or user.partner_id)
    row = get_onboarding_item(db, partner.id, item_code)
    if not row or not row.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="uploaded file not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="uploaded file not found")
    return FileResponse(path, filename=row.original_filename or path.name)


@router.post("/quotations/upload", response_model=ExternalDocumentOut)
def upload_partner_quotation(
    target_month: str | None = Form(None),
    target_start_month: str | None = Form(None),
    target_end_month: str | None = Form(None),
    issue_date: date = Form(...),
    partner_id: int | None = Form(None),
    item_name: str = Form("SES"),
    quantity: float = Form(1),
    unit_price: int = Form(0),
    work_period: str | None = Form(None),
    base_hours: str | None = Form(None),
    workplace: str | None = Form(None),
    note: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_subcontracting_user(user)
    partner = current_partner(db, user, partner_id)
    ensure_partner_direction(partner, {"downstream"}, "partner quotation")
    ensure_partner_onboarding_complete(db, partner, user)
    start_month = target_start_month or target_month
    end_month = target_end_month or target_month or start_month
    if not start_month or not end_month:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="対象開始月と対象終了月は必須です")
    validate_month_range(start_month, end_month)
    items, subtotal, tax, total = normalize_items([
        {"name": item_name or "SES", "quantity": quantity, "unit_price": unit_price}
    ])
    uploaded_path = save_partner_document_upload(file, partner, "PTQ", f"{start_month}_{end_month}")

    doc = ExternalDocument(
        partner_id=partner.id,
        document_type="partner_quotation",
        direction="downstream",
        document_no=document_no("PTQ"),
        target_month=start_month,
        issue_date=issue_date,
        subtotal=subtotal,
        tax=tax,
        total=total,
        items=items,
        file_path=uploaded_path,
        note=note,
        attributes={
            "approval_status": "pending",
            "uploaded_quotation": True,
            "original_filename": file.filename,
            "target_start_month": start_month,
            "target_end_month": end_month,
            "work_period": work_period or (start_month if start_month == end_month else f"{start_month} - {end_month}"),
            "base_hours": base_hours,
            "workplace": workplace,
        },
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    create_document_workflow(db, doc, "partner_quotation", user.id)
    db.commit()
    db.refresh(doc)
    return document_out(doc)


@router.post("/invoices/upload", response_model=ExternalDocumentOut)
def upload_partner_invoice(
    source_document_id: int = Form(...),
    payment_month: str = Form(...),
    issue_date: date = Form(...),
    partner_id: int | None = Form(None),
    amount: int = Form(...),
    item_name: str = Form("SES"),
    note: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_subcontracting_user(user)
    partner = current_partner(db, user, partner_id)
    ensure_partner_direction(partner, {"downstream"}, "partner invoice")
    quotation = approved_partner_quotation(db, partner.id, source_document_id)
    if amount < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="金額は0以上で入力してください")
    uploaded_path = save_partner_document_upload(file, partner, "PTI", payment_month)
    attrs = dict(quotation.attributes or {})
    attrs.update(
        {
            "approval_status": "pending",
            "uploaded_invoice": True,
            "original_filename": file.filename,
            "payment_month": payment_month,
            "quotation_document_no": quotation.document_no,
            "target_start_month": (quotation.attributes or {}).get("target_start_month") or quotation.target_month,
            "target_end_month": (quotation.attributes or {}).get("target_end_month") or quotation.target_month,
        }
    )
    doc = ExternalDocument(
        partner_id=partner.id,
        external_contract_id=quotation.external_contract_id,
        source_document_id=quotation.id,
        document_type="partner_invoice",
        direction="downstream",
        document_no=document_no("PTI"),
        target_month=payment_month,
        issue_date=issue_date,
        subtotal=amount,
        tax=0,
        total=amount,
        items=[{"name": item_name or "SES", "quantity": 1, "unit_price": amount, "amount": amount}],
        file_path=uploaded_path,
        note=note,
        attributes=attrs,
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    create_document_workflow(db, doc, "partner_invoice", user.id)
    db.commit()
    db.refresh(doc)
    return document_out(doc)


@router.post("/quotations", response_model=ExternalDocumentOut)
def submit_partner_quotation(
    payload: PartnerQuotationSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_subcontracting_user(user)
    partner = current_partner(db, user, payload.partner_id)
    ensure_partner_direction(partner, {"downstream"}, "partner quotation")
    ensure_partner_onboarding_complete(db, partner, user)
    items, subtotal, tax, total = normalize_items([item.model_dump() for item in payload.items])
    if not items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="quotation items are required")

    doc = ExternalDocument(
        partner_id=partner.id,
        external_contract_id=payload.external_contract_id,
        document_type="partner_quotation",
        direction="downstream",
        document_no=payload.document_no or document_no("PTQ"),
        target_month=payload.target_month,
        issue_date=payload.issue_date or date.today(),
        due_date=payload.due_date,
        subtotal=subtotal,
        tax=tax,
        total=total,
        items=items,
        note=payload.note,
        attributes={**(payload.attributes or {}), "approval_status": "pending"},
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    doc.file_path = str(create_document_file(partner, doc))
    workflow = create_workflow_request(
        db,
        workflow_type="partner_quotation",
        entity_type="external_document",
        entity_id=doc.id,
        title=f"{partner.company_name} {doc.target_month} 見積書",
        requester_id=user.id,
        attributes={"partner_id": partner.id, "document_no": doc.document_no, "target_month": doc.target_month},
        link="/approvals/contracts",
    )
    attrs = dict(doc.attributes or {})
    attrs["workflow_id"] = workflow.id
    doc.attributes = attrs
    db.commit()
    db.refresh(doc)
    return document_out(doc)
