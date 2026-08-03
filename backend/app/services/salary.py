from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contract, Employee, ProjectAssignment, Reimbursement, SalaryRecord
from app.services.offboarding import offboarding_final_month, salary_offboarding_for_month
from app.services.attendance import monthly_work_hours

EMPLOYMENT_INSURANCE_RATE = 0.0055
RECONSTRUCTION_TAX_RATE = 1.021


def current_year_month(today: date | None = None) -> str:
    value = today or date.today()
    return value.strftime("%Y-%m")


def current_contract_for_employee(db: Session, employee_id: int, today: date | None = None) -> Contract | None:
    current = today or date.today()
    contracts = list(
        db.scalars(
            select(Contract)
            .where(Contract.employee_id == employee_id)
            .where(Contract.is_deleted.is_(False))
            .order_by(Contract.start_date.desc(), Contract.created_at.desc())
        ).all()
    )
    for contract in contracts:
        starts_ok = contract.start_date is None or contract.start_date <= current
        ends_ok = contract.end_date is None or contract.end_date >= current
        if starts_ok and ends_ok:
            return contract
    return None


def int_value(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def amount_value(value: object) -> int:
    parsed = int_value(value)
    return parsed if parsed is not None else 0


def optional_amount(detail: dict, key: str) -> int | None:
    if key not in detail or detail.get(key) in (None, ""):
        return None
    return amount_value(detail.get(key))


def normalize_hours_range(value: object = None) -> tuple[float, float, str]:
    text = str(value or "140-180").lower().replace("h", "").replace(" ", "")
    text = text.replace("～", "-").replace("~", "-").replace("ー", "-")
    parts = [part for part in text.split("-") if part]
    try:
        low = float(parts[0])
        high = float(parts[1])
        if low <= 0 or high <= low:
            raise ValueError
    except (IndexError, TypeError, ValueError):
        low, high = 140.0, 180.0
    label_low = int(low) if low.is_integer() else low
    label_high = int(high) if high.is_integer() else high
    return low, high, f"{label_low}-{label_high}"


def detail_salary_settings(detail: dict | None) -> dict:
    detail = detail or {}
    low, high, hours_range = normalize_hours_range(detail.get("hours_range"))
    health_insurance = detail.get("health_insurance")
    if health_insurance is None:
        health_insurance = detail.get("insurance_fee")
    return {
        "hours_band_low": low,
        "hours_band_high": high,
        "hours_range": hours_range,
        "pension": amount_value(detail.get("pension")),
        "resident_tax": amount_value(detail.get("resident_tax")),
        "health_insurance": amount_value(health_insurance),
        "insurance_fee": amount_value(health_insurance),
        "care_insurance": amount_value(detail.get("care_insurance")),
        "employment_insurance": optional_amount(detail, "employment_insurance"),
        "income_tax": optional_amount(detail, "income_tax"),
        "other_deduction": amount_value(detail.get("other_deduction")),
        "commuting_allowance": amount_value(detail.get("commuting_allowance")),
        "other_payment": amount_value(detail.get("other_payment")),
        "employment_insurance_rate": float(detail.get("employment_insurance_rate") or EMPLOYMENT_INSURANCE_RATE),
    }


def salary_income_deduction(annual_salary: int) -> int:
    if annual_salary <= 1_625_000:
        return 550_000
    if annual_salary <= 1_800_000:
        return round(annual_salary * 0.4 - 100_000)
    if annual_salary <= 3_600_000:
        return round(annual_salary * 0.3 + 80_000)
    if annual_salary <= 6_600_000:
        return round(annual_salary * 0.2 + 440_000)
    if annual_salary <= 8_500_000:
        return round(annual_salary * 0.1 + 1_100_000)
    return 1_950_000


def income_tax_rate(taxable_income: int) -> tuple[float, int]:
    brackets = [
        (1_950_000, 0.05, 0),
        (3_300_000, 0.10, 97_500),
        (6_950_000, 0.20, 427_500),
        (9_000_000, 0.23, 636_000),
        (18_000_000, 0.33, 1_536_000),
        (40_000_000, 0.40, 2_796_000),
    ]
    for ceiling, rate, deduction in brackets:
        if taxable_income <= ceiling:
            return rate, deduction
    return 0.45, 4_796_000


def estimate_monthly_income_tax(
    taxable_monthly_salary: int,
    social_insurance_total: int,
    dependents: int = 0,
    basic_deduction: int = 480_000,
) -> int:
    taxable_base = max(taxable_monthly_salary - social_insurance_total, 0)
    annual_salary = taxable_base * 12
    dependent_deduction = max(dependents, 0) * 380_000
    annual_taxable_income = max(annual_salary - salary_income_deduction(annual_salary) - basic_deduction - dependent_deduction, 0)
    if annual_taxable_income <= 0:
        return 0
    rate, deduction = income_tax_rate(annual_taxable_income)
    annual_tax = max(round((annual_taxable_income * rate - deduction) * RECONSTRUCTION_TAX_RATE), 0)
    return round(annual_tax / 12)


def money_item(key: str, label: str, amount: int, taxable: bool = True) -> dict:
    return {"key": key, "label": label, "amount": int(amount or 0), "taxable": taxable}


def active_project_assignment_count(db: Session, employee_id: int) -> int:
    return len(
        list(
            db.scalars(
                select(ProjectAssignment.id).where(
                    ProjectAssignment.employee_id == employee_id,
                    ProjectAssignment.status == "assigned",
                )
            ).all()
        )
    )


def approved_reimbursement_amount(db: Session, employee_id: int, year_month: str | None) -> int:
    if not year_month:
        return 0
    rows = db.scalars(
        select(Reimbursement).where(
            Reimbursement.employee_id == employee_id,
            Reimbursement.pay_month == year_month,
            Reimbursement.status == "approved",
        )
    ).all()
    return sum(int(row.amount or 0) for row in rows)


def default_annual_salary_for_employee(db: Session, employee_id: int) -> int | None:
    contract = current_contract_for_employee(db, employee_id)
    if not contract or not contract.attributes:
        return None
    base_salary = int_value(contract.attributes.get("base_salary"))
    if base_salary is None:
        return None
    allowance_total = int_value(contract.attributes.get("allowance_total")) or 0
    return int((base_salary + allowance_total) * 12)


def sync_employee_annual_salary(db: Session, employee: Employee | None) -> None:
    if not employee or employee.estimated_annual_salary_manual:
        return
    annual = default_annual_salary_for_employee(db, employee.id)
    if annual is not None:
        employee.estimated_annual_salary = annual


def zero_salary_detail(employee_id: int, year_month: str | None, reason: str, offboarding=None) -> dict:
    detail = {
        "contract_id": None,
        "year_month": year_month,
        "base_salary": 0,
        "allowance_total": 0,
        "payroll_allowance_total": 0,
        "base_unit_price_low": 0,
        "base_unit_price_high": 0,
        "hours_range": "140-180",
        "hours_band_low": 140.0,
        "hours_band_high": 180.0,
        "monthly_hours": 0,
        "effective_monthly_hours": 0,
        "project_assigned": False,
        "pension": 0,
        "resident_tax": 0,
        "health_insurance": 0,
        "insurance_fee": 0,
        "care_insurance": 0,
        "employment_insurance": 0,
        "employment_insurance_rate": EMPLOYMENT_INSURANCE_RATE,
        "income_tax": 0,
        "other_deduction": 0,
        "commuting_allowance": 0,
        "other_payment": 0,
        "deduction_total": 0,
        "reimbursement_amount": 0,
        "deduction": 0,
        "overtime": 0,
        "estimated_salary": 0,
        "actual_salary_default": 0,
        "rule": reason,
        "employee_id": employee_id,
    }
    if offboarding:
        detail["offboarding"] = {
            "id": offboarding.id,
            "status": offboarding.status,
            "resignation_date": offboarding.resignation_date.isoformat(),
            "final_salary_month": offboarding_final_month(offboarding),
        }
    enrich_payroll_detail(detail)
    detail["actual_salary_default"] = 0
    return detail


def apply_offboarding_detail(detail: dict, offboarding, year_month: str | None) -> dict:
    final_month = offboarding_final_month(offboarding)
    detail["offboarding"] = {
        "id": offboarding.id,
        "status": offboarding.status,
        "resignation_date": offboarding.resignation_date.isoformat(),
        "final_salary_month": final_month,
        "final_salary_hours": offboarding.final_salary_hours,
    }
    detail["rule"] = f"offboarding_{detail.get('rule') or 'salary'}"
    if year_month == final_month and offboarding.final_salary_amount is not None:
        detail["final_salary_amount_override"] = int(offboarding.final_salary_amount)
        detail["actual_salary_default"] = int(offboarding.final_salary_amount)
    return detail


def salary_calculation_for_employee(
    db: Session,
    employee_id: int,
    monthly_hours: float | None = None,
    calculation_detail: dict | None = None,
    year_month: str | None = None,
) -> dict | None:
    offboarding = salary_offboarding_for_month(db, employee_id, year_month)
    if offboarding and year_month:
        final_month = offboarding_final_month(offboarding)
        if year_month > final_month:
            return zero_salary_detail(employee_id, year_month, "offboarding_after_final_salary", offboarding)
        if year_month == final_month and offboarding.final_salary_hours is not None:
            monthly_hours = offboarding.final_salary_hours
    contract = current_contract_for_employee(db, employee_id)
    if not contract or not contract.attributes:
        if offboarding and offboarding.final_salary_amount is not None:
            detail = zero_salary_detail(employee_id, year_month, "offboarding_final_salary_manual", offboarding)
            detail["estimated_salary"] = int(offboarding.final_salary_amount)
            detail["actual_salary_default"] = int(offboarding.final_salary_amount)
            detail["final_salary_amount_override"] = int(offboarding.final_salary_amount)
            return detail
        return None
    base_salary = int_value(contract.attributes.get("base_salary"))
    if base_salary is None:
        return None
    allowance_total = int_value(contract.attributes.get("allowance_total")) or 0
    settings = detail_salary_settings(calculation_detail)
    hours_band_low = settings["hours_band_low"]
    hours_band_high = settings["hours_band_high"]
    unit_low = round(base_salary / hours_band_high)
    unit_high = round(base_salary / hours_band_low)
    has_active_project = active_project_assignment_count(db, employee_id) > 0
    effective_monthly_hours = monthly_hours
    if monthly_hours is None and has_active_project:
        effective_monthly_hours = hours_band_low
    reimbursement_amount = approved_reimbursement_amount(db, employee_id, year_month)
    commuting_allowance = settings["commuting_allowance"]
    other_payment = settings["other_payment"]

    detail = {
        "contract_id": contract.id,
        "year_month": year_month,
        "base_salary": base_salary,
        "allowance_total": allowance_total,
        "payroll_allowance_total": 0,
        "base_unit_price_low": unit_low,
        "base_unit_price_high": unit_high,
        "hours_range": settings["hours_range"],
        "hours_band_low": hours_band_low,
        "hours_band_high": hours_band_high,
        "monthly_hours": monthly_hours,
        "effective_monthly_hours": effective_monthly_hours,
        "project_assigned": has_active_project,
        "pension": settings["pension"],
        "resident_tax": settings["resident_tax"],
        "health_insurance": settings["health_insurance"],
        "insurance_fee": settings["health_insurance"],
        "care_insurance": settings["care_insurance"],
        "employment_insurance": settings["employment_insurance"],
        "employment_insurance_rate": settings["employment_insurance_rate"],
        "income_tax": settings["income_tax"],
        "other_deduction": settings["other_deduction"],
        "commuting_allowance": commuting_allowance,
        "other_payment": other_payment,
        "deduction_total": 0,
        "reimbursement_amount": reimbursement_amount,
        "deduction": 0,
        "overtime": 0,
        "rule": "no_hours_base_only",
    }

    if not has_active_project:
        detail["estimated_salary"] = base_salary
        detail["rule"] = "no_project_base_only"
        enrich_payroll_detail(detail)
        return apply_offboarding_detail(detail, offboarding, year_month) if offboarding else detail

    if effective_monthly_hours is None:
        detail["estimated_salary"] = base_salary
        enrich_payroll_detail(detail)
        return apply_offboarding_detail(detail, offboarding, year_month) if offboarding else detail

    normal_salary = base_salary + allowance_total
    estimated = normal_salary
    detail["payroll_allowance_total"] = allowance_total
    detail["rule"] = "assigned_no_hours_allowance" if monthly_hours is None else "hours_band"

    if effective_monthly_hours < hours_band_low:
        raw_deduction = round(unit_high * (hours_band_low - effective_monthly_hours))
        deduction = min(raw_deduction, max(normal_salary - base_salary, 0))
        estimated -= deduction
        detail["deduction"] = deduction
        detail["raw_under_hours_deduction"] = raw_deduction
        detail["salary_floor"] = base_salary
        detail["salary_floor_applied"] = raw_deduction != deduction
    elif effective_monthly_hours > hours_band_high:
        overtime = round(unit_low * (effective_monthly_hours - hours_band_high))
        estimated += overtime
        detail["overtime"] = overtime

    detail["estimated_salary"] = max(round(estimated), 0)
    enrich_payroll_detail(detail)
    return apply_offboarding_detail(detail, offboarding, year_month) if offboarding else detail


def enrich_payroll_detail(detail: dict) -> None:
    estimated_salary = int(detail.get("estimated_salary") or 0)
    reimbursement_amount = int(detail.get("reimbursement_amount") or 0)
    commuting_allowance = int(detail.get("commuting_allowance") or 0)
    other_payment = int(detail.get("other_payment") or 0)
    absence_deduction = int(detail.get("deduction") or 0)
    overtime = int(detail.get("overtime") or 0)

    taxable_payment_total = max(estimated_salary + other_payment, 0)
    gross_payment_total = max(taxable_payment_total + reimbursement_amount + commuting_allowance, 0)

    pension = int(detail.get("pension") or 0)
    health_insurance = int(detail.get("health_insurance") or detail.get("insurance_fee") or 0)
    care_insurance = int(detail.get("care_insurance") or 0)
    resident_tax = int(detail.get("resident_tax") or 0)
    other_deduction = int(detail.get("other_deduction") or 0)
    employment_insurance = detail.get("employment_insurance")
    if employment_insurance is None:
        employment_insurance = round(taxable_payment_total * float(detail.get("employment_insurance_rate") or EMPLOYMENT_INSURANCE_RATE))
        detail["employment_insurance_auto"] = True
    else:
        employment_insurance = int(employment_insurance or 0)
        detail["employment_insurance_auto"] = False

    social_insurance_total = pension + health_insurance + care_insurance + employment_insurance
    income_tax = detail.get("income_tax")
    if income_tax is None:
        income_tax = estimate_monthly_income_tax(taxable_payment_total, social_insurance_total)
        detail["income_tax_auto"] = True
    else:
        income_tax = int(income_tax or 0)
        detail["income_tax_auto"] = False

    deduction_total = social_insurance_total + resident_tax + income_tax + other_deduction
    actual_salary_default = max(gross_payment_total - deduction_total, 0)

    payment_items = [
        money_item("base_salary", "基本給", detail.get("base_salary") or 0),
        money_item("allowance_total", "手当合計", detail.get("payroll_allowance_total") or 0),
        money_item("overtime", "時間外手当", overtime),
        money_item("absence_deduction", "不就労控除", -absence_deduction),
        money_item("commuting_allowance", "通勤手当（非課税）", commuting_allowance, taxable=False),
        money_item("reimbursement_amount", "経費精算", reimbursement_amount, taxable=False),
        money_item("other_payment", "その他支給", other_payment),
    ]
    deduction_items = [
        money_item("health_insurance", "健康保険", health_insurance, taxable=False),
        money_item("care_insurance", "介護保険", care_insurance, taxable=False),
        money_item("pension", "厚生年金", pension, taxable=False),
        money_item("employment_insurance", "雇用保険", employment_insurance, taxable=False),
        money_item("income_tax", "所得税", income_tax, taxable=False),
        money_item("resident_tax", "住民税", resident_tax, taxable=False),
        money_item("other_deduction", "その他控除", other_deduction, taxable=False),
    ]
    attendance_items = [
        {"label": "対象年月", "value": detail.get("year_month")},
        {"label": "月間工数", "value": detail.get("monthly_hours")},
        {"label": "基準時間帯", "value": detail.get("hours_range") or "140-180"},
        {"label": "基本単価（低）", "value": detail.get("base_unit_price_low")},
        {"label": "基本単価（高）", "value": detail.get("base_unit_price_high")},
    ]

    detail.update(
        {
            "health_insurance": health_insurance,
            "insurance_fee": health_insurance,
            "employment_insurance": employment_insurance,
            "income_tax": income_tax,
            "social_insurance_total": social_insurance_total,
            "taxable_payment_total": taxable_payment_total,
            "gross_payment_total": gross_payment_total,
            "deduction_total": deduction_total,
            "actual_salary_default": actual_salary_default,
            "payment_items": payment_items,
            "deduction_items": deduction_items,
            "attendance_items": attendance_items,
            "payroll_method": "v0.9_estimate_with_manual_override",
        }
    )


def estimated_salary_for_employee(db: Session, employee_id: int, monthly_hours: float | None = None) -> int | None:
    detail = salary_calculation_for_employee(db, employee_id, monthly_hours)
    return int(detail["estimated_salary"]) if detail else None


def recalculate_salary_record(
    db: Session,
    record: SalaryRecord,
    reset_payable: bool = False,
    reset_actual: bool = False,
    force: bool = False,
) -> SalaryRecord:
    if record.locked and not force:
        return record
    attendance_hours = monthly_work_hours(db, record.employee_id, record.year_month)
    if attendance_hours is not None:
        record.monthly_hours = attendance_hours
    detail = salary_calculation_for_employee(
        db,
        record.employee_id,
        record.monthly_hours,
        record.calculation_detail,
        record.year_month,
    )
    if not detail:
        return record
    if "monthly_hours" in detail:
        record.monthly_hours = detail.get("monthly_hours")
    record.estimated_salary = int(detail["estimated_salary"])
    record.reimbursement_amount = int(detail.get("reimbursement_amount") or 0)
    record.calculation_detail = detail
    if reset_payable or record.payable_salary is None:
        record.payable_salary = record.estimated_salary
    if reset_actual or record.actual_salary is None:
        record.actual_salary = int(detail["actual_salary_default"])
    return record


def refresh_salary_record_for_employee(
    db: Session,
    employee_id: int,
    year_month: str | None = None,
) -> SalaryRecord | None:
    employee = db.get(Employee, employee_id)
    if not employee:
        return None
    sync_employee_annual_salary(db, employee)
    month = year_month or current_year_month()
    record = db.scalar(
        select(SalaryRecord).where(SalaryRecord.employee_id == employee_id, SalaryRecord.year_month == month)
    )
    if not record:
        return ensure_salary_record(db, employee, month)
    if record.locked:
        return record

    old_default_actual = (record.calculation_detail or {}).get("actual_salary_default")
    reset_payable = record.payable_salary is None or record.payable_salary == record.estimated_salary
    reset_actual = record.actual_salary is None
    if old_default_actual is not None:
        reset_actual = reset_actual or record.actual_salary == int(old_default_actual)
    return recalculate_salary_record(db, record, reset_payable=reset_payable, reset_actual=reset_actual)


def ensure_salary_record(db: Session, employee: Employee, year_month: str | None = None) -> SalaryRecord | None:
    month = year_month or current_year_month()
    sync_employee_annual_salary(db, employee)
    attendance_hours = monthly_work_hours(db, employee.id, month)
    detail = salary_calculation_for_employee(db, employee.id, monthly_hours=attendance_hours, year_month=month)
    if detail is None:
        return None
    estimated = int(detail["estimated_salary"])

    record = db.scalar(
        select(SalaryRecord).where(SalaryRecord.employee_id == employee.id, SalaryRecord.year_month == month)
    )
    if record:
        if record.locked:
            return record
        record.monthly_hours = detail.get("monthly_hours", attendance_hours)
        recalculate_salary_record(db, record)
        return record

    record = SalaryRecord(
        employee_id=employee.id,
        year_month=month,
        monthly_hours=detail.get("monthly_hours", attendance_hours),
        estimated_salary=estimated,
        payable_salary=estimated,
        actual_salary=int(detail["actual_salary_default"]),
        reimbursement_amount=int(detail.get("reimbursement_amount") or 0),
        calculation_detail=detail,
        source="auto",
    )
    db.add(record)
    db.flush()
    return record


def ensure_salary_records(db: Session, year_month: str | None = None) -> list[SalaryRecord]:
    month = year_month or current_year_month()
    records: list[SalaryRecord] = []
    for employee in db.scalars(select(Employee).where(Employee.is_deleted.is_(False)).order_by(Employee.full_name)).all():
        record = ensure_salary_record(db, employee, month)
        if record:
            records.append(record)
    db.commit()
    return list(
        db.scalars(
            select(SalaryRecord)
            .where(SalaryRecord.year_month == month)
            .order_by(SalaryRecord.employee_id)
        ).all()
    )


def salary_record_out(record: SalaryRecord) -> dict:
    detail = record.calculation_detail or {}
    default_actual = detail.get("actual_salary_default")
    actual_manual = bool(
        default_actual is not None
        and record.actual_salary is not None
        and int(record.actual_salary) != int(default_actual)
    )
    return {
        "id": record.id,
        "employee_id": record.employee_id,
        "employee_name": record.employee.full_name if record.employee else None,
        "year_month": record.year_month,
        "monthly_hours": record.monthly_hours,
        "estimated_salary": record.estimated_salary,
        "payable_salary": record.payable_salary,
        "actual_salary": record.actual_salary,
        "actual_salary_manual": actual_manual,
        "reimbursement_amount": record.reimbursement_amount,
        "locked": record.locked,
        "estimated_annual_salary": record.employee.estimated_annual_salary if record.employee else None,
        "estimated_annual_salary_manual": record.employee.estimated_annual_salary_manual if record.employee else False,
        "hours_range": detail.get("hours_range") or "140-180",
        "pension": detail.get("pension") or 0,
        "resident_tax": detail.get("resident_tax") or 0,
        "insurance_fee": detail.get("health_insurance") or detail.get("insurance_fee") or 0,
        "health_insurance": detail.get("health_insurance") or detail.get("insurance_fee") or 0,
        "care_insurance": detail.get("care_insurance") or 0,
        "employment_insurance": detail.get("employment_insurance") or 0,
        "income_tax": detail.get("income_tax") or 0,
        "other_deduction": detail.get("other_deduction") or 0,
        "commuting_allowance": detail.get("commuting_allowance") or 0,
        "other_payment": detail.get("other_payment") or 0,
        "gross_payment_total": detail.get("gross_payment_total") or 0,
        "taxable_payment_total": detail.get("taxable_payment_total") or 0,
        "social_insurance_total": detail.get("social_insurance_total") or 0,
        "deduction_total": detail.get("deduction_total") or 0,
        "base_unit_price_low": detail.get("base_unit_price_low"),
        "base_unit_price_high": detail.get("base_unit_price_high"),
        "calculation_detail": record.calculation_detail,
        "note": record.note,
        "source": record.source,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
