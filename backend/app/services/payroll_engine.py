from datetime import date


HEALTH_STANDARD_MONTHLY = [
    58_000,
    68_000,
    78_000,
    88_000,
    98_000,
    104_000,
    110_000,
    118_000,
    126_000,
    134_000,
    142_000,
    150_000,
    160_000,
    170_000,
    180_000,
    190_000,
    200_000,
    220_000,
    240_000,
    260_000,
    280_000,
    300_000,
    320_000,
    340_000,
    360_000,
    380_000,
    410_000,
    440_000,
    470_000,
    500_000,
    530_000,
    560_000,
    590_000,
    620_000,
    650_000,
    680_000,
    710_000,
    750_000,
    790_000,
    830_000,
    880_000,
    930_000,
    980_000,
    1_030_000,
    1_090_000,
    1_150_000,
    1_210_000,
    1_270_000,
    1_330_000,
    1_390_000,
]

PENSION_STANDARD_MONTHLY = [
    88_000,
    98_000,
    104_000,
    110_000,
    118_000,
    126_000,
    134_000,
    142_000,
    150_000,
    160_000,
    170_000,
    180_000,
    190_000,
    200_000,
    220_000,
    240_000,
    260_000,
    280_000,
    300_000,
    320_000,
    340_000,
    360_000,
    380_000,
    410_000,
    440_000,
    470_000,
    500_000,
    530_000,
    560_000,
    590_000,
    620_000,
    650_000,
]

TOKYO_HEALTH_INSURANCE_RATE_2026 = 0.0985
TOKYO_CARE_INSURANCE_RATE_2026 = 0.0162
CHILD_SUPPORT_RATE_2026 = 0.0023
PENSION_RATE = 0.183
EMPLOYMENT_INSURANCE_RATE_2026 = 0.005
EMPLOYMENT_INSURANCE_RATE_2025 = 0.0055
RECONSTRUCTION_TAX_RATE = 1.021


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


def employee_age_on(birth_date: date | None, target: date | None = None) -> int | None:
    if not birth_date:
        return None
    current = target or date.today()
    return current.year - birth_date.year - ((current.month, current.day) < (birth_date.month, birth_date.day))


def date_from_year_month(year_month: str | None) -> date:
    if not year_month:
        return date.today()
    try:
        year, month = [int(part) for part in year_month.split("-", 1)]
        return date(year, month, 1)
    except (TypeError, ValueError):
        return date.today()


def standard_monthly_remuneration(amount: int, standards: list[int]) -> int:
    if amount <= standards[0]:
        return standards[0]
    for previous, current in zip(standards, standards[1:]):
        boundary = (previous + current) / 2
        if amount < boundary:
            return previous
    return standards[-1]


def employment_insurance_rate_for_month(year_month: str | None) -> float:
    target = date_from_year_month(year_month)
    if target >= date(2026, 4, 1):
        return EMPLOYMENT_INSURANCE_RATE_2026
    return EMPLOYMENT_INSURANCE_RATE_2025


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


def estimate_payroll_deductions(
    taxable_payment_total: int,
    commuting_allowance: int = 0,
    year_month: str | None = None,
    birth_date: date | None = None,
    dependents: int = 0,
) -> dict:
    target = date_from_year_month(year_month)
    age = employee_age_on(birth_date, target)
    insurance_base = max(int(taxable_payment_total or 0) + int(commuting_allowance or 0), 0)
    if insurance_base <= 0 and int(taxable_payment_total or 0) <= 0:
        employment_rate = employment_insurance_rate_for_month(year_month)
        return {
            "insurance_base": 0,
            "health_standard_monthly": 0,
            "pension_standard_monthly": 0,
            "health_insurance": 0,
            "care_insurance": 0,
            "pension": 0,
            "employment_insurance": 0,
            "employment_insurance_rate": employment_rate,
            "income_tax": 0,
            "dependents": dependents,
            "age": age,
            "prefecture": "東京",
            "method": "jp_2026_tokyo_standard_remuneration_estimate",
            "rates": {
                "health_insurance": TOKYO_HEALTH_INSURANCE_RATE_2026,
                "child_support": CHILD_SUPPORT_RATE_2026,
                "care_insurance": TOKYO_CARE_INSURANCE_RATE_2026,
                "pension": PENSION_RATE,
                "employment_insurance": employment_rate,
            },
        }
    health_standard = standard_monthly_remuneration(insurance_base, HEALTH_STANDARD_MONTHLY)
    pension_standard = standard_monthly_remuneration(insurance_base, PENSION_STANDARD_MONTHLY)
    has_care_insurance = age is not None and 40 <= age <= 64

    health_insurance = round(health_standard * (TOKYO_HEALTH_INSURANCE_RATE_2026 + CHILD_SUPPORT_RATE_2026) / 2)
    care_insurance = round(health_standard * TOKYO_CARE_INSURANCE_RATE_2026 / 2) if has_care_insurance else 0
    pension = round(pension_standard * PENSION_RATE / 2)
    employment_rate = employment_insurance_rate_for_month(year_month)
    employment_insurance = round(taxable_payment_total * employment_rate)
    social_total = health_insurance + care_insurance + pension + employment_insurance
    income_tax = estimate_monthly_income_tax(taxable_payment_total, social_total, dependents)

    return {
        "insurance_base": insurance_base,
        "health_standard_monthly": health_standard,
        "pension_standard_monthly": pension_standard,
        "health_insurance": health_insurance,
        "care_insurance": care_insurance,
        "pension": pension,
        "employment_insurance": employment_insurance,
        "employment_insurance_rate": employment_rate,
        "income_tax": income_tax,
        "dependents": dependents,
        "age": age,
        "prefecture": "東京",
        "method": "jp_2026_tokyo_standard_remuneration_estimate",
        "rates": {
            "health_insurance": TOKYO_HEALTH_INSURANCE_RATE_2026,
            "child_support": CHILD_SUPPORT_RATE_2026,
            "care_insurance": TOKYO_CARE_INSURANCE_RATE_2026,
            "pension": PENSION_RATE,
            "employment_insurance": employment_rate,
        },
    }
