import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


EMPLOYEE_NATIONALITIES = {"中国", "日本", "その他"}
GRADUATION_STATUSES = {"大学卒業", "短大卒業", "大学院修了", "中退・その他"}
CONTRACT_TYPES = {"正社員", "契約社員", "freelance", "アルバイト", "その他"}
CONTRACT_COMPANIES = {"日本インフォテック株式会社", "その他"}
PROJECT_NATIONALITY_REQUIREMENTS = {"日本籍のみ", "制限なし"}
EMPLOYEE_TYPES = {"一般社員", "hr", "総務", "営業", "管理者"}
PARTNER_TYPES = {"upstream", "downstream", "both"}
EXTERNAL_DIRECTIONS = {"upstream", "downstream", "both"}
EXTERNAL_DOCUMENT_TYPES = {"purchase_order", "quotation", "invoice", "uploaded_contract", "partner_quotation", "partner_invoice"}
REIMBURSEMENT_TYPES = {"交通費", "出張費", "懇親会費", "その他"}
REIMBURSEMENT_STATUSES = {"pending", "approved", "rejected"}

NAME_PATTERN = re.compile(r"^[A-Za-z\u3040-\u30ff\u3400-\u9fff々〆ヶ・ー\s\u3000.'-]+$")
JP_PHONE_PATTERN = re.compile(r"^(?:\+81[- ]?)?(?:0?\d{1,4}[- ]?\d{1,4}[- ]?\d{3,4})$")


def validate_employee_name(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("姓名为必填项")
    if not NAME_PATTERN.fullmatch(text):
        raise ValueError("姓名只能包含日文、汉字或英文")
    return text


def validate_jp_phone(value: str) -> str:
    text = value.strip()
    compact = re.sub(r"[-\s]", "", text)
    normalized = compact.replace("+81", "0", 1) if compact.startswith("+81") else compact
    if not JP_PHONE_PATTERN.fullmatch(text) or not normalized.startswith("0") or len(normalized) not in {10, 11}:
        raise ValueError("电话格式需符合日本地区电话规则")
    return text


class SkillItem(BaseModel):
    name: str
    level: str = Field(default="中", description="高/中/低")


class UserOut(BaseModel):
    id: int
    email: EmailStr
    login_id: str | None = None
    full_name: str
    role: str
    employee_id: int | None = None
    partner_id: int | None = None
    must_reset_password: bool = False

    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class TeamsSsoIn(BaseModel):
    email: EmailStr
    full_name: str | None = None


class EmployeeBase(BaseModel):
    code: str | None = None
    full_name: str
    name_kana: str | None = None
    birth_date: date | None = None
    graduation_status: str | None = None
    residence: str | None = None
    nearest_station: str | None = None
    email: EmailStr
    phone: str | None = None
    age: int | None = None
    languages: str | None = None
    certifications: str | None = None
    technical_experience: str | None = None
    it_years: float | None = None
    talent_category: str | None = None
    skills: list[SkillItem] = Field(default_factory=list)
    nationality: str | None = None
    employee_type: str | None = "一般社員"
    estimated_annual_salary: int | None = Field(default=None, ge=0)
    estimated_annual_salary_manual: bool = False


class EmployeeCreate(EmployeeBase):
    birth_date: date
    graduation_status: str
    phone: str
    nationality: str

    @field_validator("full_name")
    @classmethod
    def full_name_format(cls, value: str) -> str:
        return validate_employee_name(value)

    @field_validator("phone")
    @classmethod
    def phone_format(cls, value: str) -> str:
        return validate_jp_phone(value)

    @field_validator("nationality")
    @classmethod
    def nationality_option(cls, value: str) -> str:
        if value not in EMPLOYEE_NATIONALITIES:
            raise ValueError("国籍必须从下拉选项中选择")
        return value

    @field_validator("graduation_status")
    @classmethod
    def graduation_option(cls, value: str) -> str:
        if value not in GRADUATION_STATUSES:
            raise ValueError("毕业状态必须从下拉选项中选择")
        return value

    @field_validator("employee_type")
    @classmethod
    def employee_type_option(cls, value: str | None) -> str:
        text = value or "一般社員"
        if text not in EMPLOYEE_TYPES:
            raise ValueError("员工类型必须从下拉选项中选择")
        return text


class EmployeeUpdate(BaseModel):
    code: str | None = None
    full_name: str | None = None
    name_kana: str | None = None
    birth_date: date | None = None
    graduation_status: str | None = None
    residence: str | None = None
    nearest_station: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    age: int | None = None
    languages: str | None = None
    certifications: str | None = None
    technical_experience: str | None = None
    it_years: float | None = None
    talent_category: str | None = None
    skills: list[SkillItem] | None = None
    nationality: str | None = None
    employee_type: str | None = None
    estimated_annual_salary: int | None = Field(default=None, ge=0)
    estimated_annual_salary_manual: bool | None = None

    @field_validator("full_name")
    @classmethod
    def full_name_format(cls, value: str | None) -> str | None:
        return validate_employee_name(value) if value is not None else value

    @field_validator("phone")
    @classmethod
    def phone_format(cls, value: str | None) -> str | None:
        return validate_jp_phone(value) if value else value

    @field_validator("nationality")
    @classmethod
    def nationality_option(cls, value: str | None) -> str | None:
        if value and value not in EMPLOYEE_NATIONALITIES:
            raise ValueError("国籍必须从下拉选项中选择")
        return value

    @field_validator("graduation_status")
    @classmethod
    def graduation_option(cls, value: str | None) -> str | None:
        if value and value not in GRADUATION_STATUSES:
            raise ValueError("毕业状态必须从下拉选项中选择")
        return value

    @field_validator("employee_type")
    @classmethod
    def employee_type_option(cls, value: str | None) -> str | None:
        if value and value not in EMPLOYEE_TYPES:
            raise ValueError("员工类型必须从下拉选项中选择")
        return value


class EmployeeSelfUpdate(BaseModel):
    phone: str | None = None
    nearest_station: str | None = None
    languages: str | None = None
    certifications: str | None = None
    technical_experience: str | None = None
    it_years: float | None = Field(default=None, ge=0)
    talent_category: str | None = None
    skills: list[SkillItem] | None = None

    @field_validator("phone")
    @classmethod
    def phone_format(cls, value: str | None) -> str | None:
        return validate_jp_phone(value) if value else value


class EmployeeOut(EmployeeBase):
    id: int
    platform_email: str | None = None
    salary_sync: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeOffboardingBase(BaseModel):
    employee_id: int | None = None
    resignation_date: date
    last_work_date: date | None = None
    resignation_reason: str
    reason_detail: str | None = None
    handover_note: str | None = None
    final_salary_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    final_salary_hours: float | None = Field(default=None, ge=0)
    final_salary_amount: int | None = Field(default=None, ge=0)
    final_salary_note: str | None = None

    @field_validator("resignation_reason")
    @classmethod
    def offboarding_reason_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("resignation reason is required")
        return text


class EmployeeOffboardingCreate(EmployeeOffboardingBase):
    pass


class EmployeeOffboardingUpdate(BaseModel):
    resignation_date: date | None = None
    last_work_date: date | None = None
    resignation_reason: str | None = None
    reason_detail: str | None = None
    handover_note: str | None = None
    final_salary_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    final_salary_hours: float | None = Field(default=None, ge=0)
    final_salary_amount: int | None = Field(default=None, ge=0)
    final_salary_note: str | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def offboarding_status_option(cls, value: str | None) -> str | None:
        if value and value not in {"pending", "approved", "scheduled", "completed", "rejected", "cancelled"}:
            raise ValueError("invalid offboarding status")
        return value


class EmployeeOffboardingOut(BaseModel):
    id: int
    employee_id: int
    full_name: str
    name_kana: str | None = None
    email: str
    phone: str | None = None
    residence: str | None = None
    nearest_station: str | None = None
    employee_type: str | None = None
    resignation_date: date
    last_work_date: date | None = None
    resignation_reason: str
    reason_detail: str | None = None
    handover_note: str | None = None
    final_salary_month: str
    final_salary_hours: float | None = None
    final_salary_amount: int | None = None
    final_salary_note: str | None = None
    status: str
    requester_id: int | None = None
    requester_name: str | None = None
    approver_id: int | None = None
    approver_name: str | None = None
    approved_at: datetime | None = None
    processed_at: datetime | None = None
    attributes: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractBase(BaseModel):
    employee_id: int
    title: str
    contract_type: str
    vendor_company: str
    start_date: date | None = None
    end_date: date | None = None
    pdf_filename: str | None = None
    parsed_text: str | None = None
    attributes: dict | None = None

    @field_validator("contract_type")
    @classmethod
    def contract_type_option(cls, value: str) -> str:
        if value not in CONTRACT_TYPES:
            raise ValueError("契约类型必须从下拉选项中选择")
        return value

    @field_validator("vendor_company")
    @classmethod
    def vendor_company_option(cls, value: str) -> str:
        if value not in CONTRACT_COMPANIES:
            raise ValueError("契约公司必须从下拉选项中选择")
        return value


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    employee_id: int | None = None
    title: str | None = None
    contract_type: str | None = None
    vendor_company: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    parsed_text: str | None = None
    attributes: dict | None = None

    @field_validator("contract_type")
    @classmethod
    def contract_type_option(cls, value: str | None) -> str | None:
        if value and value not in CONTRACT_TYPES:
            raise ValueError("契约类型必须从下拉选项中选择")
        return value

    @field_validator("vendor_company")
    @classmethod
    def vendor_company_option(cls, value: str | None) -> str | None:
        if value and value not in CONTRACT_COMPANIES:
            raise ValueError("契约公司必须从下拉选项中选择")
        return value


class ContractOut(ContractBase):
    id: int
    pdf_download_url: str | None = None
    salary_sync: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalaryRecordUpdate(BaseModel):
    monthly_hours: float | None = Field(default=None, ge=0)
    hours_range: str | None = "140-180"
    pension: int | None = Field(default=None, ge=0)
    resident_tax: int | None = Field(default=None, ge=0)
    insurance_fee: int | None = Field(default=None, ge=0)
    health_insurance: int | None = Field(default=None, ge=0)
    care_insurance: int | None = Field(default=None, ge=0)
    employment_insurance: int | None = Field(default=None, ge=0)
    income_tax: int | None = Field(default=None, ge=0)
    other_deduction: int | None = Field(default=None, ge=0)
    commuting_allowance: int | None = Field(default=None, ge=0)
    other_payment: int | None = Field(default=None, ge=0)
    payable_salary: int | None = Field(default=None, ge=0)
    actual_salary: int | None = Field(default=None, ge=0)
    estimated_annual_salary: int | None = Field(default=None, ge=0)
    locked: bool | None = None
    note: str | None = None


class SalaryRecordOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    employee_email: str | None = None
    employee_is_deleted: bool = False
    year_month: str
    monthly_hours: float | None = None
    estimated_salary: int
    payable_salary: int | None = None
    actual_salary: int | None = None
    actual_salary_manual: bool = False
    reimbursement_amount: int = 0
    locked: bool = False
    estimated_annual_salary: int | None = None
    estimated_annual_salary_manual: bool = False
    hours_range: str = "140-180"
    pension: int = 0
    resident_tax: int = 0
    insurance_fee: int = 0
    health_insurance: int = 0
    care_insurance: int = 0
    employment_insurance: int = 0
    income_tax: int = 0
    other_deduction: int = 0
    commuting_allowance: int = 0
    other_payment: int = 0
    gross_payment_total: int = 0
    taxable_payment_total: int = 0
    social_insurance_total: int = 0
    deduction_total: int = 0
    base_unit_price_low: int | None = None
    base_unit_price_high: int | None = None
    calculation_detail: dict | None = None
    note: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceSettingsIn(BaseModel):
    default_start_time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    default_end_time: str = Field(default="18:00", pattern=r"^\d{2}:\d{2}$")
    break_minutes: int = Field(default=60, ge=0, le=240)
    hour_step: float = Field(default=0.5, ge=0.25, le=1)
    default_paid_leave_days: float = Field(default=10.0, ge=0)
    paid_leave_counts_as_work: bool = False
    leave_policies: dict | None = None
    company_holidays: list | None = None


class AttendanceSettingsOut(AttendanceSettingsIn):
    id: int
    default_daily_hours: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkCalendarDayOut(BaseModel):
    id: int
    work_date: date
    is_workday: bool
    holiday_name: str | None = None
    source: str
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkCalendarDayUpdate(BaseModel):
    is_workday: bool
    holiday_name: str | None = None
    note: str | None = None


class AttendanceRequestCreate(BaseModel):
    employee_id: int | None = None
    work_date: date
    request_type: str
    requested_hours: float | None = Field(default=None, ge=0)
    reason: str | None = None


class AttendanceDecisionIn(BaseModel):
    status: str
    comment: str | None = None

    @model_validator(mode="after")
    def rejection_comment_required(self):
        if self.status == "rejected" and not (self.comment or "").strip():
            raise ValueError("却下理由を入力してください")
        return self


class AttendanceLeaveBalanceIn(BaseModel):
    employee_id: int
    fiscal_year: int
    granted_days: float = Field(default=10.0, ge=0)
    adjustment_days: float = 0
    note: str | None = None


class AttendanceLeaveBalanceOut(BaseModel):
    id: int | None = None
    employee_id: int
    employee_name: str | None = None
    fiscal_year: int
    granted_days: float
    adjustment_days: float
    used_days: float
    remaining_days: float
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AttendanceRequestOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    work_date: date
    year_month: str
    request_type: str
    requested_hours: float | None = None
    calculated_hours: float | None = None
    status: str
    reason: str | None = None
    requester_name: str | None = None
    approver_name: str | None = None
    approved_at: datetime | None = None
    salary_locked: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceSummaryRow(BaseModel):
    employee_id: int
    employee_name: str
    year_month: str
    scheduled_workdays: int
    scheduled_hours: float
    actual_work_hours: float
    paid_leave_used_days: float
    paid_leave_remaining_days: float
    pending_requests: int
    salary_locked: bool = False


class AttendanceSummaryOut(BaseModel):
    year_month: str
    settings: AttendanceSettingsOut
    rows: list[AttendanceSummaryRow]


class ProjectBase(BaseModel):
    client_company: str
    project_name: str
    description: str
    required_skills: list[str] = Field(default_factory=list)
    workplace: str
    nationality_requirement: str | None = None
    duration: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    headcount: int | None = None
    unit_price: str | None = None
    source_email_subject: str | None = None
    raw_email: str | None = None
    attachment_name: str | None = None
    attributes: dict | None = None

    @field_validator("client_company", "project_name", "workplace")
    @classmethod
    def required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("甲方公司名、案件项目名、工作场所为必填项")
        return text


class ProjectCreate(ProjectBase):
    @field_validator("nationality_requirement")
    @classmethod
    def nationality_requirement_option(cls, value: str | None) -> str | None:
        if value and value not in PROJECT_NATIONALITY_REQUIREMENTS:
            raise ValueError("国籍要求必须从下拉选项中选择")
        return value


class ProjectUpdate(BaseModel):
    client_company: str | None = None
    project_name: str | None = None
    description: str | None = None
    required_skills: list[str] | None = None
    workplace: str | None = None
    nationality_requirement: str | None = None
    duration: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    headcount: int | None = None
    unit_price: str | None = None
    source_email_subject: str | None = None
    raw_email: str | None = None
    attachment_name: str | None = None
    attributes: dict | None = None

    @field_validator("client_company", "project_name", "workplace")
    @classmethod
    def required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        text = value.strip()
        if not text:
            raise ValueError("甲方公司名、案件项目名、工作场所为必填项")
        return text

    @field_validator("nationality_requirement")
    @classmethod
    def nationality_requirement_option(cls, value: str | None) -> str | None:
        if value and value not in PROJECT_NATIONALITY_REQUIREMENTS:
            raise ValueError("国籍要求必须从下拉选项中选择")
        return value


class ProjectOut(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailAnalyzeIn(BaseModel):
    subject: str | None = None
    body: str
    attachment_text: str | None = None


class CandidateScore(BaseModel):
    employee: EmployeeOut
    score: float
    reasons: list[str]


class AssignmentCreate(BaseModel):
    employee_id: int
    role: str | None = None
    status: str = "assigned"


class AssignmentUpdate(BaseModel):
    project_id: int | None = None
    employee_id: int | None = None
    role: str | None = None
    status: str | None = None


class AssignmentOut(BaseModel):
    id: int
    project_id: int
    employee_id: int
    employee_name: str
    role: str | None = None
    status: str
    salary_sync: dict | None = None
    created_at: datetime


class BusinessPartnerBase(BaseModel):
    company_name: str
    company_kana: str | None = None
    partner_type: str = "both"
    contracted_at: date | None = None
    contract_end_date: date | None = None
    terminated: bool = False
    status: str = "active"
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    bank_info: dict | None = None
    note: str | None = None
    attributes: dict | None = None

    @field_validator("company_name")
    @classmethod
    def partner_name_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("公司名为必填项")
        return text

    @field_validator("partner_type")
    @classmethod
    def partner_type_option(cls, value: str) -> str:
        if value not in PARTNER_TYPES:
            raise ValueError("取引先方向必须为 upstream/downstream/both")
        return value


class BusinessPartnerCreate(BusinessPartnerBase):
    pass


class BusinessPartnerUpdate(BaseModel):
    company_name: str | None = None
    company_kana: str | None = None
    partner_type: str | None = None
    contracted_at: date | None = None
    contract_end_date: date | None = None
    terminated: bool | None = None
    status: str | None = None
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    bank_info: dict | None = None
    note: str | None = None
    attributes: dict | None = None

    @field_validator("company_name")
    @classmethod
    def partner_name_required(cls, value: str | None) -> str | None:
        if value is None:
            return value
        text = value.strip()
        if not text:
            raise ValueError("公司名为必填项")
        return text

    @field_validator("partner_type")
    @classmethod
    def partner_type_option(cls, value: str | None) -> str | None:
        if value and value not in PARTNER_TYPES:
            raise ValueError("取引先方向必须为 upstream/downstream/both")
        return value


class BusinessPartnerOut(BusinessPartnerBase):
    id: int
    contract_active: bool = True
    partner_login_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExternalContractBase(BaseModel):
    partner_id: int | None = None
    direction: str
    title: str
    contract_type: str = "ses_basic"
    status: str = "draft"
    contracted_at: date | None = None
    note: str | None = None
    attributes: dict | None = None

    @field_validator("direction")
    @classmethod
    def direction_option(cls, value: str) -> str:
        if value not in EXTERNAL_DIRECTIONS:
            raise ValueError("契约方向必须为 upstream/downstream")
        return value

    @field_validator("title")
    @classmethod
    def external_contract_title_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("契约标题为必填项")
        return text


class ExternalContractCreate(BaseModel):
    company_name: str
    direction: str
    title: str
    contract_type: str = "ses_basic"
    status: str = "draft"
    contracted_at: date | None = None
    contracted_success: bool = False
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    note: str | None = None
    attributes: dict | None = None

    @field_validator("company_name")
    @classmethod
    def company_name_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("公司名为必填项")
        return text

    @field_validator("direction")
    @classmethod
    def direction_option(cls, value: str) -> str:
        if value not in EXTERNAL_DIRECTIONS:
            raise ValueError("契约方向必须为 upstream/downstream")
        return value

    @field_validator("title")
    @classmethod
    def external_contract_title_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("契约标题为必填项")
        return text


class ExternalContractUpdate(BaseModel):
    partner_id: int | None = None
    direction: str | None = None
    title: str | None = None
    contract_type: str | None = None
    status: str | None = None
    contracted_at: date | None = None
    contracted_success: bool | None = None
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    note: str | None = None
    attributes: dict | None = None

    @field_validator("direction")
    @classmethod
    def direction_option(cls, value: str | None) -> str | None:
        if value and value not in EXTERNAL_DIRECTIONS:
            raise ValueError("契约方向必须为 upstream/downstream")
        return value


class ExternalContractOut(ExternalContractBase):
    id: int
    partner_name: str | None = None
    contracted_success: bool = False
    partner_login_id: str | None = None
    partner_temporary_password: str | None = None
    download_token: str | None = None
    file_paths: list | None = None
    fixed_file_links: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExternalDocumentItem(BaseModel):
    name: str
    quantity: float = Field(default=1, ge=0)
    unit_price: int = Field(default=0, ge=0)
    amount: int | None = Field(default=None, ge=0)
    description: str | None = None


class ExternalDocumentGenerateIn(BaseModel):
    partner_id: int
    external_contract_id: int | None = None
    source_document_id: int | None = None
    document_no: str | None = None
    target_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    issue_date: date
    due_date: date | None = None
    items: list[ExternalDocumentItem] = Field(default_factory=list)
    note: str | None = None
    attributes: dict | None = None


class PartnerQuotationSubmitIn(ExternalDocumentGenerateIn):
    partner_id: int | None = None


class PartnerOnboardingItemOut(BaseModel):
    id: int | None = None
    partner_id: int
    item_code: str
    name: str
    filename: str | None = None
    template_download_url: str | None = None
    upload_download_url: str | None = None
    status: str = "pending"
    form_data: dict | None = None
    original_filename: str | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class PartnerOnboardingFormIn(BaseModel):
    form_data: dict


class ExternalDocumentOut(BaseModel):
    id: int
    partner_id: int
    partner_name: str | None = None
    external_contract_id: int | None = None
    source_document_id: int | None = None
    document_type: str
    direction: str
    document_no: str
    target_month: str
    issue_date: date
    due_date: date | None = None
    subtotal: int
    tax: int
    total: int
    items: list | None = None
    file_path: str | None = None
    note: str | None = None
    attributes: dict | None = None
    settlement_confirmed: bool = True
    settlement_actual_amount: int | None = None
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExternalDocumentSettlementUpdate(BaseModel):
    settlement_confirmed: bool = True
    settlement_actual_amount: int = Field(default=0, ge=0)


class WorkflowRequestOut(BaseModel):
    id: int
    workflow_type: str
    entity_type: str
    entity_id: int
    title: str
    status: str
    requester_id: int | None = None
    requester_name: str | None = None
    approver_id: int | None = None
    approver_name: str | None = None
    submitted_at: datetime
    decided_at: datetime | None = None
    comment: str | None = None
    attributes: dict | None = None
    entity: dict | None = None
    can_process: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowDecisionIn(BaseModel):
    status: str
    comment: str | None = None

    @field_validator("status")
    @classmethod
    def status_option(cls, value: str) -> str:
        if value not in {"approved", "rejected"}:
            raise ValueError("status must be approved or rejected")
        return value

    @model_validator(mode="after")
    def rejection_comment_required(self):
        if self.status == "rejected" and not (self.comment or "").strip():
            raise ValueError("却下理由を入力してください")
        return self


class ReimbursementBase(BaseModel):
    expense_type: str
    period_start_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    period_end_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    employee_id: int | None = None
    amount: int = Field(ge=0)
    pay_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    note: str | None = None

    @field_validator("expense_type")
    @classmethod
    def expense_type_option(cls, value: str) -> str:
        if value not in REIMBURSEMENT_TYPES:
            raise ValueError("経費種別はリストから選択してください")
        return value


class ReimbursementCreate(ReimbursementBase):
    pass


class ReimbursementUpdate(BaseModel):
    expense_type: str | None = None
    period_start_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    period_end_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    employee_id: int | None = None
    amount: int | None = Field(default=None, ge=0)
    pay_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    note: str | None = None

    @field_validator("expense_type")
    @classmethod
    def expense_type_option(cls, value: str | None) -> str | None:
        if value and value not in REIMBURSEMENT_TYPES:
            raise ValueError("経費種別はリストから選択してください")
        return value


class ReimbursementOut(BaseModel):
    id: int
    expense_type: str
    period_start_month: str
    period_end_month: str
    employee_id: int
    employee_name: str | None = None
    amount: int
    pay_month: str
    status: str
    invoice_file_paths: list | None = None
    invoice_files: list[dict] = Field(default_factory=list)
    note: str | None = None
    requester_id: int | None = None
    requester_name: str | None = None
    approver_id: int | None = None
    approver_name: str | None = None
    approved_at: datetime | None = None
    attributes: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExternalPersonnelOut(BaseModel):
    id: int
    partner_id: int
    partner_name: str | None = None
    full_name: str
    company_name: str
    assignment_month: str
    contract_end_date: date | None = None
    monthly_hours: float | None = None
    resume_download_url: str | None = None
    avatar_download_url: str | None = None
    timesheet_download_url: str | None = None
    status: str
    note: str | None = None
    attributes: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExternalPersonnelUpdate(BaseModel):
    full_name: str | None = None
    assignment_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    contract_end_date: date | None = None
    monthly_hours: float | None = Field(default=None, ge=0)
    status: str | None = None
    note: str | None = None


class ExternalPersonnelStatusIn(BaseModel):
    status: str
    note: str | None = None

    @field_validator("status")
    @classmethod
    def status_option(cls, value: str) -> str:
        if value not in {"submitted", "confirmed", "rejected"}:
            raise ValueError("status must be submitted, confirmed, or rejected")
        return value

    @model_validator(mode="after")
    def rejection_note_required(self):
        if self.status == "rejected" and not (self.note or "").strip():
            raise ValueError("却下理由を入力してください")
        return self


class MonthlySettlementOut(BaseModel):
    id: int
    year_month: str
    invoice_total: int
    purchase_order_total: int
    salary_total: int
    net_income: int
    detail: dict | None = None
    locked: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HomepageOut(BaseModel):
    user: UserOut
    employee: EmployeeOut | None
    partner: BusinessPartnerOut | None = None
    company_profile: dict | None = None
    current_contract: ContractOut | None = None
    contracts: list[ContractOut]
    projects: list[ProjectOut]
    salary: SalaryRecordOut | None = None
    permissions: dict[str, list[str]]
    ui_permissions: list[str] = Field(default_factory=list)


class UiPermissionUpdate(BaseModel):
    route_keys: list[str] = Field(default_factory=list)


class UiPermissionOut(BaseModel):
    roles: list[str]
    items: list[str]
    permissions: dict[str, list[str]]
    locked_roles: list[str] = Field(default_factory=list)


class AiAssistantConfigOut(BaseModel):
    enabled: bool
    provider: str
    title: str
    greeting: str
    app_url: str | None = None
    supports_conversation: bool = True


class AiAssistantChatIn(BaseModel):
    message: str
    conversation_id: str | None = None
    inputs: dict | None = None


class AiAssistantChatOut(BaseModel):
    answer: str
    conversation_id: str | None = None
    provider: str
    message_id: str | None = None
    task_id: str | None = None
    metadata: dict | None = None
    sources: list[dict] = Field(default_factory=list)


class MailSettingsIn(BaseModel):
    provider: str = "disabled"
    enabled: bool = False
    imap_enabled: bool = False
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: str | None = None
    imap_folder: str = "INBOX"
    poll_interval_seconds: int = 60
    smtp_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: EmailStr | None = None
    smtp_use_tls: bool = True


class MailSettingsOut(BaseModel):
    provider: str
    enabled: bool
    imap_enabled: bool
    imap_host: str | None
    imap_port: int
    imap_username: str | None
    has_imap_password: bool
    imap_folder: str
    poll_interval_seconds: int
    smtp_enabled: bool
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    has_smtp_password: bool
    smtp_from: EmailStr | None
    smtp_use_tls: bool


class MailTestOut(BaseModel):
    ok: bool
    message: str


class NotificationRuleUpdate(BaseModel):
    enabled: bool
    channels: list[str] = Field(default_factory=list)
    recipient_roles: list[str] = Field(default_factory=list)
    recipient_user_ids: list[int] = Field(default_factory=list)
    include_related: bool = True
    schedule: dict = Field(default_factory=dict)


class WorkflowDefinitionUpdate(BaseModel):
    enabled: bool
    steps: list[dict] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, value: list[dict]) -> list[dict]:
        if not value:
            raise ValueError("承認ステップを1件以上設定してください")
        normalized: list[dict] = []
        for index, step in enumerate(value, start=1):
            roles = sorted({str(item) for item in step.get("roles", []) if item})
            user_ids = sorted({int(item) for item in step.get("user_ids", []) if str(item).isdigit()})
            if not roles and not user_ids:
                raise ValueError(f"承認ステップ{index}にロールまたは担当者を設定してください")
            normalized.append({
                "kind": "user" if user_ids and not roles else "role",
                "roles": roles,
                "user_ids": user_ids,
                "label": str(step.get("label") or f"承認ステップ{index}"),
            })
        return normalized


class DocumentAccessPolicyUpdate(BaseModel):
    allowed_roles: list[str] = Field(default_factory=list)
    owner_access: bool = True
    related_access: bool = False


class EmployeeProfileChangeIn(BaseModel):
    full_name: str | None = None
    name_kana: str | None = None
    birth_date: date | None = None
    graduation_status: str | None = None
    residence: str | None = None
    email: EmailStr | None = None
    nationality: str | None = None
    reason: str | None = None

    @field_validator("full_name")
    @classmethod
    def profile_full_name_format(cls, value: str | None) -> str | None:
        return validate_employee_name(value) if value is not None else value

    @field_validator("nationality")
    @classmethod
    def profile_nationality_option(cls, value: str | None) -> str | None:
        if value and value not in EMPLOYEE_NATIONALITIES:
            raise ValueError("国籍は選択肢から選んでください")
        return value

    @field_validator("graduation_status")
    @classmethod
    def profile_graduation_option(cls, value: str | None) -> str | None:
        if value and value not in GRADUATION_STATUSES:
            raise ValueError("卒業区分は選択肢から選んでください")
        return value

    @model_validator(mode="after")
    def at_least_one_change(self):
        if not (self.model_fields_set - {"reason"}):
            raise ValueError("変更する項目を1件以上入力してください")
        return self
