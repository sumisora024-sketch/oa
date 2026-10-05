from datetime import date

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db import Base, engine
from app.models import Contract, Employee, Project, User
from app.services.pdf_parser import parse_contract_attributes
from app.services.public_capabilities import ensure_public_capability_defaults
from app.services.salary import sync_employee_annual_salary


def init_db() -> None:
    db = Session(engine)
    try:
        seed_admin(db)
        seed_sample_data(db)
        ensure_public_capability_defaults(db)
        ensure_employee_login(db, "吴臻清", "employee")
        normalize_existing_data(db)
        db.commit()
    finally:
        db.close()


def ensure_schema_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        if engine.dialect.name == "mysql":
            for table in table_names:
                conn.execute(text(f"ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        if "employees" in table_names:
            employee_columns = {column["name"] for column in inspector.get_columns("employees")}
            if "employee_type" not in employee_columns:
                conn.execute(text("ALTER TABLE employees ADD COLUMN employee_type VARCHAR(32) NULL"))
            if "estimated_annual_salary" not in employee_columns:
                conn.execute(text("ALTER TABLE employees ADD COLUMN estimated_annual_salary INT NULL"))
            if "estimated_annual_salary_manual" not in employee_columns:
                conn.execute(text("ALTER TABLE employees ADD COLUMN estimated_annual_salary_manual BOOL NOT NULL DEFAULT 0"))
            if "is_deleted" not in employee_columns:
                conn.execute(text("ALTER TABLE employees ADD COLUMN is_deleted BOOL NOT NULL DEFAULT 0"))
            if "deleted_at" not in employee_columns:
                conn.execute(text("ALTER TABLE employees ADD COLUMN deleted_at DATETIME NULL"))
            employee_indexes = {index["name"] for index in inspector.get_indexes("employees")}
            duplicate = conn.execute(
                text("SELECT full_name, email, COUNT(*) c FROM employees GROUP BY full_name, email HAVING c > 1 LIMIT 1")
            ).fetchone()
            if not duplicate and "uq_employee_full_name_email" not in employee_indexes:
                conn.execute(text("CREATE UNIQUE INDEX uq_employee_full_name_email ON employees (full_name, email)"))
        if "users" in table_names:
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "must_reset_password" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN must_reset_password BOOL NOT NULL DEFAULT 0"))
            if "login_id" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN login_id VARCHAR(255) NULL"))
            if "partner_id" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN partner_id INT NULL"))
            user_indexes = {index["name"] for index in inspector.get_indexes("users")}
            if "ix_users_login_id" not in user_indexes:
                conn.execute(text("CREATE UNIQUE INDEX ix_users_login_id ON users (login_id)"))
        if "salary_records" in table_names:
            salary_columns = {column["name"] for column in inspector.get_columns("salary_records")}
            if "monthly_hours" not in salary_columns:
                conn.execute(text("ALTER TABLE salary_records ADD COLUMN monthly_hours FLOAT NULL"))
            if "payable_salary" not in salary_columns:
                conn.execute(text("ALTER TABLE salary_records ADD COLUMN payable_salary INT NULL"))
            if "calculation_detail" not in salary_columns:
                conn.execute(text("ALTER TABLE salary_records ADD COLUMN calculation_detail JSON NULL"))
            if "reimbursement_amount" not in salary_columns:
                conn.execute(text("ALTER TABLE salary_records ADD COLUMN reimbursement_amount INT NOT NULL DEFAULT 0"))
            if "locked" not in salary_columns:
                conn.execute(text("ALTER TABLE salary_records ADD COLUMN locked BOOL NOT NULL DEFAULT 0"))
            salary_indexes = {index["name"] for index in inspector.get_indexes("salary_records")}
            ym_column = "`year_month`" if engine.dialect.name == "mysql" else "year_month"
            duplicate_salary = conn.execute(
                text(f"SELECT employee_id, {ym_column}, COUNT(*) c FROM salary_records GROUP BY employee_id, {ym_column} HAVING c > 1 LIMIT 1")
            ).fetchone()
            if not duplicate_salary and "uq_salary_employee_month" not in salary_indexes:
                conn.execute(text(f"CREATE UNIQUE INDEX uq_salary_employee_month ON salary_records (employee_id, {ym_column})"))
        if "contracts" in table_names:
            contract_columns = {column["name"] for column in inspector.get_columns("contracts")}
            if "is_deleted" not in contract_columns:
                conn.execute(text("ALTER TABLE contracts ADD COLUMN is_deleted BOOL NOT NULL DEFAULT 0"))
            if "deleted_at" not in contract_columns:
                conn.execute(text("ALTER TABLE contracts ADD COLUMN deleted_at DATETIME NULL"))


def seed_admin(db: Session) -> None:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.app_admin_email))
    if user:
        return
    employee = Employee(
        full_name="システム管理者",
        name_kana="システムカンリシャ",
        email=settings.app_admin_email,
        phone="0000000000",
        birth_date=date(1990, 1, 1),
        graduation_status="大学卒業",
        residence="Tokyo",
        nearest_station="Tokyo",
        age=36,
        nationality="その他",
        employee_type="管理者",
        skills=[{"name": "oa", "level": "高"}],
    )
    db.add(employee)
    db.flush()
    db.add(
        User(
            email=settings.app_admin_email,
            full_name="システム管理者",
        role="admin",
        password_hash=get_password_hash(settings.app_admin_password),
        must_reset_password=False,
        employee_id=employee.id,
        )
    )


def seed_sample_data(db: Session) -> None:
    if db.scalar(select(Project).limit(1)):
        return
    project = Project(
        client_company="サンプルクライアント株式会社",
        project_name="OA 初期構築案件",
        description="FastAPI + Vue + MySQL + Redis による社内 OA 初期構築。",
        required_skills=["python", "vue", "mysql", "redis"],
        workplace="半在宅 / 東京",
        nationality_requirement="",
        duration="長期",
        headcount=2,
        unit_price="待确认",
    )
    db.add(project)


def ensure_employee_login(db: Session, full_name: str, role: str) -> None:
    settings = get_settings()
    employee = db.scalar(select(Employee).where(Employee.full_name == full_name))
    if not employee:
        return
    user = db.scalar(select(User).where(User.employee_id == employee.id))
    if user:
        user.role = role
        user.is_active = True
        return
    db.add(
        User(
            email=employee.email,
            full_name=employee.full_name,
            role=role,
            password_hash=get_password_hash(settings.default_employee_password),
            employee_id=employee.id,
        )
    )


def normalize_existing_data(db: Session) -> None:
    graduation_map = {
        "大学毕业": "大学卒業",
        "短大毕业": "短大卒業",
        "研究生/大学院": "大学院修了",
        "肄业或其他": "中退・その他",
        "未填写": "中退・その他",
    }
    employee_type_map = {
        "普通员工": "一般社員",
        "营业": "営業",
        "管理员": "管理者",
    }
    contract_type_map = {
        "正社员": "正社員",
        "契约社员": "契約社員",
        "其他": "その他",
    }
    project_nationality_map = {"日籍のみ": "日本籍のみ", "无限制": "制限なし"}
    for employee in db.scalars(select(Employee)).all():
        employee.graduation_status = graduation_map.get(employee.graduation_status, employee.graduation_status)
        if employee.graduation_status not in {"大学卒業", "短大卒業", "大学院修了", "中退・その他"}:
            employee.graduation_status = "大学卒業"
        if not employee.nationality:
            employee.nationality = "その他"
        elif employee.nationality == "其他":
            employee.nationality = "その他"
        if not employee.employee_type:
            employee.employee_type = "一般社員"
        employee.employee_type = employee_type_map.get(employee.employee_type, employee.employee_type)
        if employee.is_deleted is None:
            employee.is_deleted = False
        if employee.birth_date:
            today = date.today()
            employee.age = today.year - employee.birth_date.year - ((today.month, today.day) < (employee.birth_date.month, employee.birth_date.day))

    for contract in db.scalars(select(Contract)).all():
        if not contract.end_date:
            contract.end_date = date(9999, 12, 31)
        if contract.parsed_text:
            attrs = parse_contract_attributes(contract.parsed_text)
            contract.attributes = {**(contract.attributes or {}), **attrs}
        contract.contract_type = contract_type_map.get(contract.contract_type, contract.contract_type)
        if contract.contract_type not in {"正社員", "契約社員", "freelance", "アルバイト", "その他"}:
            contract.contract_type = "その他"
        if contract.vendor_company == "其他":
            contract.vendor_company = "その他"
        if contract.vendor_company not in {"日本インフォテック株式会社", "その他"}:
            contract.vendor_company = "その他"
        sync_employee_annual_salary(db, contract.employee)

    for project in db.scalars(select(Project)).all():
        project.nationality_requirement = project_nationality_map.get(
            project.nationality_requirement,
            project.nationality_requirement,
        )

    for user in db.scalars(select(User)).all():
        if user.must_reset_password is None:
            user.must_reset_password = False
