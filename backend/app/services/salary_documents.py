from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Employee, SalaryRecord


JP_FONT = "HeiseiKakuGo-W5"


def ensure_japanese_font() -> None:
    try:
        pdfmetrics.getFont(JP_FONT)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))


def yen(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{int(value):,} 円"


def text(value: object) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def base_styles() -> dict:
    ensure_japanese_font()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="JPTitle", fontName=JP_FONT, fontSize=18, leading=24, alignment=1, textColor=colors.HexColor("#0f3f5f")))
    styles.add(ParagraphStyle(name="JPSection", fontName=JP_FONT, fontSize=12, leading=16, textColor=colors.HexColor("#17324d"), spaceAfter=5))
    styles.add(ParagraphStyle(name="JPBody", fontName=JP_FONT, fontSize=9, leading=13, textColor=colors.HexColor("#20242a")))
    styles.add(ParagraphStyle(name="JPNote", fontName=JP_FONT, fontSize=8, leading=12, textColor=colors.HexColor("#667085")))
    return styles


def section_title(title: str, styles: dict) -> Paragraph:
    return Paragraph(title, styles["JPSection"])


def build_salary_pdf(record: SalaryRecord, employee: Employee | None) -> BytesIO:
    styles = base_styles()
    detail = record.calculation_detail or {}
    calculated_actual = detail.get("actual_salary_default")
    manual_adjustment = None
    if calculated_actual is not None and record.actual_salary is not None:
        manual_adjustment = int(record.actual_salary) - int(calculated_actual)
    has_manual_adjustment = bool(manual_adjustment)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
    )

    payment_items = detail.get("payment_items") or []
    deduction_items = detail.get("deduction_items") or []
    attendance_rows = [
        ["対象年月", record.year_month],
        ["氏名", employee.full_name if employee else str(record.employee_id)],
        ["月間工数", text(record.monthly_hours)],
        ["基準時間帯", text(detail.get("hours_range") or "140-180")],
        ["基本単価（低）", yen(detail.get("base_unit_price_low"))],
        ["基本単価（高）", yen(detail.get("base_unit_price_high"))],
    ]

    summary_rows = [
        ["対象年月", record.year_month, "氏名", employee.full_name if employee else str(record.employee_id)],
        ["総支給額", yen(detail.get("gross_payment_total")), "控除合計", yen(detail.get("deduction_total"))],
    ]
    if has_manual_adjustment:
        summary_rows.append(["計算差引支給額", yen(calculated_actual), "手動調整額", yen(manual_adjustment)])
    summary_rows.append(["差引支給額", yen(record.actual_salary), "課税支給額", yen(detail.get("taxable_payment_total"))])

    story = [
        Paragraph("給与明細書", styles["JPTitle"]),
        Spacer(1, 5 * mm),
        _summary_table(summary_rows),
        Spacer(1, 7 * mm),
        section_title("勤怠", styles),
        _table(attendance_rows, [32 * mm, 58 * mm]),
        Spacer(1, 7 * mm),
        section_title("支給", styles),
        _amount_table(payment_items, fallback_rows=[
            ["基本給", yen(detail.get("base_salary"))],
            ["手当合計", yen(detail.get("payroll_allowance_total") or 0)],
            ["経費精算", yen(record.reimbursement_amount)],
        ]),
        Spacer(1, 7 * mm),
        section_title("控除", styles),
        _amount_table(deduction_items, fallback_rows=[
            ["健康保険", yen(detail.get("health_insurance") or detail.get("insurance_fee") or 0)],
            ["厚生年金", yen(detail.get("pension") or 0)],
            ["雇用保険", yen(detail.get("employment_insurance") or 0)],
            ["所得税", yen(detail.get("income_tax") or 0)],
            ["住民税", yen(detail.get("resident_tax") or 0)],
        ]),
        Spacer(1, 7 * mm),
        _total_table(record, detail),
        Spacer(1, 5 * mm),
        Paragraph("本明細はNIT OA Systemに登録された契約、勤怠、経費精算データを基に作成されています。税額は概算値または手動調整値を含む場合があります。", styles["JPNote"]),
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer


def build_annual_salary_pdf(employee: Employee) -> BytesIO:
    styles = base_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=20 * mm)
    rows = [
        ["氏名", employee.full_name],
        ["想定年収", yen(employee.estimated_annual_salary)],
        ["算定区分", "手動設定" if employee.estimated_annual_salary_manual else "自動算定"],
    ]
    story = [
        Paragraph("想定年収確認書", styles["JPTitle"]),
        Spacer(1, 10 * mm),
        _table(rows, [42 * mm, 105 * mm]),
        Spacer(1, 12 * mm),
        Paragraph("本書は社内OAシステムに登録された情報に基づき出力されています。", styles["JPBody"]),
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer


def _summary_table(rows: list[list[str]]) -> Table:
    table = Table(rows, colWidths=[28 * mm, 54 * mm, 28 * mm, 54 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), JP_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7fafc")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f2f7")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e8f2f7")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _amount_table(items: list[dict], fallback_rows: list[list[str]]) -> Table:
    rows = [[item.get("label") or item.get("key"), yen(item.get("amount") or 0)] for item in items if int(item.get("amount") or 0) != 0]
    if not rows:
        rows = fallback_rows
    return _table(rows, [72 * mm, 74 * mm], amount_column=1)


def _total_table(record: SalaryRecord, detail: dict) -> Table:
    calculated_actual = detail.get("actual_salary_default")
    manual_adjustment = None
    if calculated_actual is not None and record.actual_salary is not None:
        manual_adjustment = int(record.actual_salary) - int(calculated_actual)
    rows = [
        ["総支給額", yen(detail.get("gross_payment_total"))],
        ["控除合計", yen(detail.get("deduction_total"))],
        ["計算差引支給額", yen(calculated_actual)],
    ]
    if manual_adjustment:
        rows.append(["手動調整額", yen(manual_adjustment)])
    rows.append(["差引支給額", yen(record.actual_salary)])
    table = _table(rows, [72 * mm, 74 * mm], amount_column=1)
    final_row = len(rows) - 1
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, final_row), (-1, final_row), colors.HexColor("#dff7f5")),
                ("FONTSIZE", (0, final_row), (-1, final_row), 11),
            ]
        )
    )
    return table


def _table(rows: list[list[str]], col_widths: list[float], amount_column: int | None = None) -> Table:
    table = Table(rows, colWidths=col_widths)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), JP_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#20242a")),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if amount_column is not None:
        style.append(("ALIGN", (amount_column, 0), (amount_column, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    return table
