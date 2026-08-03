from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="employee")
    login_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_reset_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("business_partners.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="user", foreign_keys=[employee_id])
    partner = relationship("BusinessPartner", back_populates="partner_users", foreign_keys=[partner_id])


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("full_name", "email", name="uq_employee_full_name_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_kana: Mapped[str | None] = mapped_column(String(120), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    graduation_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    residence: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nearest_station: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    languages: Mapped[str | None] = mapped_column(Text, nullable=True)
    certifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    it_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    talent_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employee_type: Mapped[str | None] = mapped_column(String(32), nullable=True, default="一般社員")
    estimated_annual_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_annual_salary_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="employee", uselist=False, foreign_keys="User.employee_id")
    contracts = relationship("Contract", back_populates="employee", cascade="all, delete-orphan")
    assignments = relationship("ProjectAssignment", back_populates="employee", cascade="all, delete-orphan")
    salary_records = relationship("SalaryRecord", back_populates="employee", cascade="all, delete-orphan")
    reimbursements = relationship("Reimbursement", back_populates="employee", cascade="all, delete-orphan")

    @property
    def platform_email(self) -> str | None:
        return self.user.email if self.user else None


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vendor_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    pdf_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="contracts")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_company: Mapped[str] = mapped_column(String(255), nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    workplace: Mapped[str] = mapped_column(String(255), nullable=False)
    nationality_requirement: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_email_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    assignments = relationship("ProjectAssignment", back_populates="project", cascade="all, delete-orphan")


class ProjectAssignment(Base):
    __tablename__ = "project_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="assigned")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="assignments")
    employee = relationship("Employee", back_populates="assignments")


class SalaryRecord(Base):
    __tablename__ = "salary_records"
    __table_args__ = (UniqueConstraint("employee_id", "year_month", name="uq_salary_employee_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    monthly_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_salary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payable_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reimbursement_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    calculation_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="auto")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="salary_records")


class AttendanceSetting(Base):
    __tablename__ = "attendance_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    default_start_time: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    default_end_time: Mapped[str] = mapped_column(String(5), nullable=False, default="18:00")
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    hour_step: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    default_paid_leave_days: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    paid_leave_counts_as_work: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    leave_policies: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    company_holidays: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class WorkCalendarDay(Base):
    __tablename__ = "work_calendar_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    is_workday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    holiday_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AttendanceRequest(Base):
    __tablename__ = "attendance_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])
    requester = relationship("User", foreign_keys=[requester_id])
    approver = relationship("User", foreign_keys=[approver_id])


class AttendanceLeaveBalance(Base):
    __tablename__ = "attendance_leave_balances"
    __table_args__ = (UniqueConstraint("employee_id", "fiscal_year", name="uq_attendance_leave_employee_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    granted_days: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    adjustment_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])


class Reimbursement(Base):
    __tablename__ = "reimbursements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    expense_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    period_start_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    period_end_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pay_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    invoice_file_paths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="reimbursements")
    requester = relationship("User", foreign_keys=[requester_id])
    approver = relationship("User", foreign_keys=[approver_id])


class EmployeeOffboarding(Base):
    __tablename__ = "employee_offboardings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name_kana: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    residence: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nearest_station: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resignation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_work_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resignation_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    handover_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_salary_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    final_salary_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_salary_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_salary_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])
    requester = relationship("User", foreign_keys=[requester_id])
    approver = relationship("User", foreign_keys=[approver_id])


class BusinessPartner(Base):
    __tablename__ = "business_partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    partner_type: Mapped[str] = mapped_column(String(32), nullable=False, default="both")
    contracted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    external_contracts = relationship("ExternalContract", back_populates="partner", cascade="all, delete-orphan")
    documents = relationship("ExternalDocument", back_populates="partner")
    partner_users = relationship("User", back_populates="partner", foreign_keys="User.partner_id")
    external_personnel = relationship("ExternalPersonnel", back_populates="partner", cascade="all, delete-orphan")
    onboarding_items = relationship("PartnerOnboardingItem", back_populates="partner", cascade="all, delete-orphan")


class PartnerOnboardingItem(Base):
    __tablename__ = "partner_onboarding_items"
    __table_args__ = (UniqueConstraint("partner_id", "item_code", name="uq_partner_onboarding_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("business_partners.id"), nullable=False, index=True)
    item_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    form_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    partner = relationship("BusinessPartner", back_populates="onboarding_items")
    updater = relationship("User", foreign_keys=[updated_by])


class ExternalContract(Base):
    __tablename__ = "external_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("business_partners.id"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(64), nullable=False, default="ses_basic")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    contracted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    download_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    file_paths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    partner = relationship("BusinessPartner", back_populates="external_contracts")
    documents = relationship("ExternalDocument", back_populates="external_contract")


class ExternalDocument(Base):
    __tablename__ = "external_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("business_partners.id"), nullable=False, index=True)
    external_contract_id: Mapped[int | None] = mapped_column(ForeignKey("external_contracts.id"), nullable=True, index=True)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("external_documents.id"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    document_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    partner = relationship("BusinessPartner", back_populates="documents")
    external_contract = relationship("ExternalContract", back_populates="documents")
    source_document = relationship("ExternalDocument", remote_side=[id])


class MonthlySettlement(Base):
    __tablename__ = "monthly_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    year_month: Mapped[str] = mapped_column(String(7), unique=True, nullable=False, index=True)
    invoice_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_order_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    salary_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_income: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class WorkflowRequest(Base):
    __tablename__ = "workflow_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    requester = relationship("User", foreign_keys=[requester_id])
    approver = relationship("User", foreign_keys=[approver_id])


class ExternalPersonnel(Base):
    __tablename__ = "external_personnel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("business_partners.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assignment_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    monthly_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timesheet_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    partner = relationship("BusinessPartner", back_populates="external_personnel")
    creator = relationship("User", foreign_keys=[created_by])
    confirmer = relationship("User", foreign_keys=[confirmed_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    module: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UiRolePermission(Base):
    __tablename__ = "ui_role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    route_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    updater = relationship("User", foreign_keys=[updated_by])


class DocumentArchive(Base):
    __tablename__ = "document_archives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    directory_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_month: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    missing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MailSettings(Base):
    __tablename__ = "mail_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="disabled")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    imap_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    imap_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    imap_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    imap_folder: Mapped[str] = mapped_column(String(120), nullable=False, default="INBOX")
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    smtp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_from: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
