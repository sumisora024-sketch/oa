import re
from datetime import datetime
from typing import BinaryIO

from pypdf import PdfReader


def extract_text_from_pdf(file_obj: BinaryIO) -> str:
    reader = PdfReader(file_obj)
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)
    return "\n".join(parts).strip()


def parse_contract_attributes(text: str) -> dict:
    attrs: dict[str, str | None] = {}
    period_match = re.search(
        r"契約期間\s*(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})日?\s*[～~-]?\s*(?:(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})日?)?",
        text,
    )
    if period_match:
        parts = period_match.groups()
        try:
            attrs["start_date"] = datetime(int(parts[0]), int(parts[1]), int(parts[2])).date().isoformat()
            attrs["end_date"] = datetime(int(parts[3]), int(parts[4]), int(parts[5])).date().isoformat() if parts[3] else None
        except ValueError:
            attrs["start_date"] = None
            attrs["end_date"] = None
    if "契約社員" in text or "contract" in text.lower():
        attrs["contract_type"] = "契約社員"
    elif "正社員" in text or "正社员" in text:
        attrs["contract_type"] = "正社員"

    company_match = re.search(r"(?:甲方|委託元|会社名|公司名|名\s*称)[:：\s]*([^\n\r]+)", text)
    attrs["vendor_company"] = company_match.group(1).strip() if company_match else None
    workplace_match = re.search(r"就業の場所\s*([^\n\r]+)", text)
    attrs["workplace"] = workplace_match.group(1).strip() if workplace_match else None
    duty_match = re.search(r"従事する業務の内容\s*([^\n\r]+)", text)
    attrs["duty"] = duty_match.group(1).strip() if duty_match else None
    salary_attrs = parse_salary_attributes(text)
    attrs.update(salary_attrs)
    return attrs


def parse_money(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def parse_salary_attributes(text: str) -> dict:
    base_salary = None
    allowances: list[dict[str, int | str]] = []

    base_match = re.search(r"基本給\s*([0-9,，]+)\s*円", text)
    if base_match:
        base_salary = parse_money(base_match.group(1))

    for name, amount in re.findall(r"[①-⑳]?\s*([^:\n\r：]*手当)\s*[:：]?\s*月額\s*([0-9,，]+)\s*円", text):
        money = parse_money(amount)
        if money is not None:
            allowances.append({"name": name.strip(), "amount": money})

    allowance_total = sum(int(item["amount"]) for item in allowances)
    result: dict[str, object] = {
        "base_salary": base_salary,
        "allowances": allowances,
        "allowance_total": allowance_total if allowances else None,
        "salary_total_monthly": (base_salary or 0) + allowance_total if base_salary is not None else None,
    }
    if base_salary:
        result["base_unit_price_low"] = round(base_salary / 180)
        result["base_unit_price_high"] = round(base_salary / 140)
    return result
