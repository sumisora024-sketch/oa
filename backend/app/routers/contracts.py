import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.core.config import ROOT_DIR, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Contract, Employee, SalaryRecord, User
from app.schemas import ContractCreate, ContractOut, ContractUpdate, SalaryRecordOut, SalaryRecordUpdate
from app.services.pdf_parser import extract_text_from_pdf, parse_contract_attributes
from app.services.contract_reminders import LONG_TERM_END_DATE, send_contract_due_reminders
from app.services.salary import current_year_month, ensure_salary_record, ensure_salary_records, recalculate_salary_record, refresh_salary_record_for_employee, refresh_salary_records_for_employee, salary_record_out, sync_employee_annual_salary
from app.services.salary_documents import build_annual_salary_pdf, build_salary_pdf
from app.services.salary_signals import register_salary_refresh

router = APIRouter(prefix="/contracts", tags=["contracts"])
CONTRACT_PDF_DIR = ROOT_DIR / "backend" / "storage" / "contracts"


def can_access_contract(user: User, contract: Contract) -> bool:
    if user.role in {"admin", "soumu", "hr"}:
        return True
    return user.employee_id == contract.employee_id


def salary_out(record: SalaryRecord) -> dict:
    return salary_record_out(record)


def normalize_contract_attributes(value: dict | None) -> dict:
    attrs = dict(value or {})
    allowances = []
    for item in attrs.get("allowances") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        amount = max(int(item.get("amount") or 0), 0)
        if name or amount:
            allowances.append({"name": name or "手当", "amount": amount})
    attrs["allowances"] = allowances
    allowance_total = sum(item["amount"] for item in allowances)
    attrs["allowance_total"] = allowance_total
    base_salary = attrs.get("base_salary")
    if base_salary not in (None, ""):
        base_salary = max(int(base_salary), 0)
        attrs["base_salary"] = base_salary
        attrs["salary_total_monthly"] = base_salary + allowance_total
        hours_match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-～]\s*(\d+(?:\.\d+)?)\s*", str(attrs.get("hours_range") or "140-180"))
        if hours_match:
            lower = float(hours_match.group(1))
            upper = float(hours_match.group(2))
            if lower > 0 and upper >= lower:
                attrs["hours_range"] = f"{lower:g}-{upper:g}"
                attrs["base_unit_price_low"] = round(base_salary / upper)
                attrs["base_unit_price_high"] = round(base_salary / lower)
    else:
        attrs["base_salary"] = None
        attrs["salary_total_monthly"] = None
        attrs["base_unit_price_low"] = None
        attrs["base_unit_price_high"] = None
    return attrs


def store_contract_pdf(file: UploadFile, contract_id: int) -> str:
    CONTRACT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    original = Path(file.filename or "contract.pdf").name
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", original).strip("_") or "contract.pdf"
    path = CONTRACT_PDF_DIR / f"contract_{contract_id}_{int(datetime.utcnow().timestamp())}_{safe_name}"
    file.file.seek(0)
    with path.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    return str(path)


@router.get("", response_model=list[ContractOut])
def list_contracts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role in {"admin", "soumu", "hr"}:
        return list(db.scalars(select(Contract).where(Contract.is_deleted.is_(False)).order_by(Contract.created_at.desc())).all())
    if user.role == "employee" and user.employee_id:
        return list(
            db.scalars(
                select(Contract)
                .where(Contract.employee_id == user.employee_id, Contract.is_deleted.is_(False))
                .order_by(Contract.created_at.desc())
            ).all()
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


@router.post("", response_model=ContractOut)
def create_contract(payload: ContractCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "soumu", "hr"})
    employee = db.get(Employee, payload.employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    data = payload.model_dump()
    data["end_date"] = data.get("end_date") or LONG_TERM_END_DATE
    data["attributes"] = normalize_contract_attributes(data.get("attributes"))
    contract = Contract(**data)
    db.add(contract)
    db.flush()
    sync_employee_annual_salary(db, employee)
    contract.salary_sync = refresh_salary_records_for_employee(db, employee.id, reason="contract_created")
    db.commit()
    db.refresh(contract)
    return contract


@router.post("/import-pdf", response_model=ContractOut)
def import_pdf_contract(
    employee_id: int = Form(...),
    title: str = Form("雇用契約書"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "soumu", "hr"})
    employee = db.get(Employee, employee_id)
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在")
    text = extract_text_from_pdf(file.file)
    attrs = parse_contract_attributes(text)
    contract = Contract(
        employee_id=employee_id,
        title=title,
        contract_type=attrs.get("contract_type") or "その他",
        vendor_company=attrs.get("vendor_company") if attrs.get("vendor_company") == "日本インフォテック株式会社" else "その他",
        start_date=date.fromisoformat(attrs["start_date"]) if attrs.get("start_date") else None,
        end_date=date.fromisoformat(attrs["end_date"]) if attrs.get("end_date") else LONG_TERM_END_DATE,
        pdf_filename=file.filename,
        parsed_text=text,
        attributes=normalize_contract_attributes(attrs),
    )
    db.add(contract)
    db.flush()
    contract.pdf_path = store_contract_pdf(file, contract.id)
    sync_employee_annual_salary(db, employee)
    contract.salary_sync = refresh_salary_records_for_employee(db, employee.id, reason="contract_imported")
    db.commit()
    db.refresh(contract)
    return contract


@router.get("/reminders/due", response_model=list[ContractOut])
def due_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "soumu", "hr"})
    today = date.today()
    soon = today + timedelta(days=30)
    stmt = select(Contract).where(
        Contract.is_deleted.is_(False),
        Contract.end_date >= today,
        Contract.end_date <= soon,
        Contract.end_date != LONG_TERM_END_DATE,
    )
    return list(db.scalars(stmt).all())


@router.post("/reminders/send")
def send_due_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "soumu", "hr"})
    return {"sent": send_contract_due_reminders(), "recipient": get_settings().hr_reminder_email}


@router.get("/salaries", response_model=list[SalaryRecordOut])
def list_salaries(
    year_month: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "soumu", "hr"})
    return [salary_out(record) for record in ensure_salary_records(db, year_month or current_year_month())]


@router.put("/salaries/{record_id}", response_model=SalaryRecordOut)
def update_salary(
    record_id: int,
    payload: SalaryRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_role(user, {"admin", "soumu", "hr"})
    record = db.get(SalaryRecord, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工资记录不存在")
    updates = payload.model_dump(exclude_unset=True)
    if record.locked and updates.get("locked") is not False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="給与がロックされています。解除してから編集してください")
    next_locked = updates.pop("locked", None)
    unlocking = record.locked and next_locked is False
    if unlocking:
        record.locked = False
    if "estimated_annual_salary" in updates:
        annual = updates.pop("estimated_annual_salary")
        if record.employee:
            record.employee.estimated_annual_salary = annual
            record.employee.estimated_annual_salary_manual = annual is not None
    updates.pop("monthly_hours", None)
    detail_keys = {
        "hours_range",
        "pension",
        "resident_tax",
        "insurance_fee",
        "health_insurance",
        "care_insurance",
        "employment_insurance",
        "income_tax",
        "other_deduction",
        "commuting_allowance",
        "other_payment",
    }
    detail_updates = {key: updates.pop(key) for key in list(updates.keys()) if key in detail_keys}
    if "insurance_fee" in detail_updates and "health_insurance" not in detail_updates:
        detail_updates["health_insurance"] = detail_updates["insurance_fee"]
    old_default_actual = (record.calculation_detail or {}).get("actual_salary_default")
    salary_inputs_changed = bool(detail_updates) or unlocking
    if detail_updates:
        detail = dict(record.calculation_detail or {})
        manual_deductions = set(detail.get("manual_deductions") or [])
        deduction_keys = {
            "pension",
            "health_insurance",
            "insurance_fee",
            "care_insurance",
            "employment_insurance",
            "income_tax",
        }
        for key, value in detail_updates.items():
            if key not in deduction_keys:
                continue
            canonical = "health_insurance" if key == "insurance_fee" else key
            old_value = detail.get(canonical)
            if canonical == "health_insurance" and old_value is None:
                old_value = detail.get("insurance_fee")
            if old_value is None and value not in (None, "", 0):
                manual_deductions.add(canonical)
            elif old_value is not None and int(value or 0) != int(old_value or 0):
                manual_deductions.add(canonical)
        detail.update(detail_updates)
        detail["manual_deductions"] = sorted(manual_deductions)
        record.calculation_detail = detail
    if (
        salary_inputs_changed
        and "actual_salary" in updates
        and old_default_actual is not None
        and updates["actual_salary"] == old_default_actual
    ):
        updates.pop("actual_salary")
    for key, value in updates.items():
        setattr(record, key, value)
    reset_actual = False
    if salary_inputs_changed and "actual_salary" not in updates:
        reset_actual = record.actual_salary is None
        if old_default_actual is not None:
            reset_actual = reset_actual or record.actual_salary == int(old_default_actual)
    recalculate_salary_record(
        db,
        record,
        reset_payable=salary_inputs_changed and "payable_salary" not in updates,
        reset_actual=reset_actual,
    )
    if next_locked is True:
        record.locked = True
    register_salary_refresh(
        db,
        record.employee_id,
        months={record.year_month},
        include_current=False,
        reason="salary_record_updated",
    )
    db.commit()
    db.refresh(record)
    return salary_out(record)


@router.get("/salaries/self", response_model=SalaryRecordOut)
def get_my_salary(
    year_month: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未绑定人员信息")
    employee = db.get(Employee, user.employee_id)
    record = ensure_salary_record(db, employee, year_month or current_year_month()) if employee else None
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工资记录不存在")
    db.commit()
    db.refresh(record)
    return salary_out(record)


@router.get("/salaries/{record_id}/payslip.pdf")
def download_salary_pdf(record_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = db.get(SalaryRecord, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工资记录不存在")
    if user.role not in {"admin", "soumu", "hr"} and user.employee_id != record.employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    if not record.locked:
        refreshed = refresh_salary_record_for_employee(db, record.employee_id, record.year_month)
        if refreshed:
            record = refreshed
            db.commit()
            db.refresh(record)
    buffer = build_salary_pdf(record, record.employee)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=salary-{record.employee_id}-{record.year_month}-{int(datetime.utcnow().timestamp())}.pdf",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/salaries/{record_id}/annual-estimate.pdf")
def download_annual_salary_pdf(record_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = db.get(SalaryRecord, record_id)
    if not record or not record.employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工资记录不存在")
    if user.role not in {"admin", "soumu", "hr"} and user.employee_id != record.employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    sync_employee_annual_salary(db, record.employee)
    db.commit()
    buffer = build_annual_salary_pdf(record.employee)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=annual-salary-{record.employee_id}-{int(datetime.utcnow().timestamp())}.pdf",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract(contract_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    contract = db.get(Contract, contract_id)
    if not contract or contract.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="契约不存在")
    if not can_access_contract(user, contract):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return contract


@router.get("/{contract_id}/pdf/download")
def download_contract_pdf(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contract = db.get(Contract, contract_id)
    if not contract or contract.is_deleted or not contract.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="契約PDFが見つかりません")
    if not can_access_contract(user, contract):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="権限がありません")
    path = Path(contract.pdf_path).resolve()
    storage_root = CONTRACT_PDF_DIR.resolve()
    if not path.is_relative_to(storage_root) or not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="契約PDFが見つかりません")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=contract.pdf_filename or path.name,
        headers={"Cache-Control": "private, no-store"},
    )


@router.put("/{contract_id}", response_model=ContractOut)
def update_contract(contract_id: int, payload: ContractUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "soumu", "hr"})
    contract = db.get(Contract, contract_id)
    if not contract or contract.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="契约不存在")
    updates = payload.model_dump(exclude_unset=True)
    previous_employee_id = contract.employee_id
    if "employee_id" in updates:
        target_employee = db.get(Employee, updates["employee_id"])
        if not target_employee or target_employee.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社員が見つかりません")
    if "parsed_text" in updates and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="解析テキストを編集できるのは管理者のみです")
    if "attributes" in updates:
        updates["attributes"] = normalize_contract_attributes(updates["attributes"])
    for key, value in updates.items():
        if key == "end_date" and value is None:
            value = LONG_TERM_END_DATE
        setattr(contract, key, value)
    affected_employee_ids = {previous_employee_id, contract.employee_id}
    salary_sync = []
    for employee_id in affected_employee_ids:
        employee = db.get(Employee, employee_id)
        if employee and not employee.is_deleted:
            sync_employee_annual_salary(db, employee)
            salary_sync.append(
                refresh_salary_records_for_employee(db, employee.id, reason="contract_updated")
            )
    contract.salary_sync = {"employees": salary_sync}
    db.commit()
    db.refresh(contract)
    return contract


@router.delete("/{contract_id}")
def delete_contract(contract_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin", "soumu", "hr"})
    contract = db.get(Contract, contract_id)
    if not contract or contract.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="契约不存在")
    employee_id = contract.employee_id
    contract.is_deleted = True
    contract.deleted_at = datetime.utcnow()
    contract.attributes = {**(contract.attributes or {}), "deleted": True}
    db.flush()
    salary_sync = refresh_salary_records_for_employee(db, employee_id, reason="contract_deleted")
    db.commit()
    return {"ok": True, "salary_sync": salary_sync}
