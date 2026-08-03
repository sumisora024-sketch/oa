from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UiRolePermission


UI_ROLES = ["admin", "hr", "pm", "employee", "partner"]

UI_ROUTE_KEYS = [
    "home",
    "employees.internal",
    "employees.external",
    "employees.offboarding",
    "contracts.internal",
    "contracts.external.new",
    "contracts.external.partners",
    "documents.purchase_orders",
    "documents.quotations",
    "documents.invoices",
    "documents.history",
    "documents.library",
    "approvals.contracts",
    "approvals.reimbursements",
    "approvals.attendance",
    "approvals.offboarding",
    "reimbursements.claims",
    "reimbursements.salaries",
    "reimbursements.monthly_settlement",
    "subcontracting.notice",
    "subcontracting.quotations",
    "subcontracting.invoices",
    "subcontracting.personnel",
    "attendance.summary",
    "attendance.requests",
    "attendance.settings",
    "projects",
    "settings.mail",
    "settings.permissions",
]


DEFAULT_UI_PERMISSIONS: dict[str, set[str]] = {
    "admin": set(UI_ROUTE_KEYS),
    "hr": {
        "home",
        "employees.internal",
        "employees.external",
        "employees.offboarding",
        "contracts.internal",
        "approvals.contracts",
        "approvals.reimbursements",
        "approvals.attendance",
        "approvals.offboarding",
        "reimbursements.claims",
        "reimbursements.salaries",
        "attendance.summary",
        "attendance.requests",
        "attendance.settings",
    },
    "pm": {
        "home",
        "employees.internal",
        "employees.offboarding",
        "contracts.external.new",
        "contracts.external.partners",
        "documents.purchase_orders",
        "documents.quotations",
        "documents.invoices",
        "documents.history",
        "approvals.contracts",
        "reimbursements.claims",
        "reimbursements.monthly_settlement",
        "attendance.summary",
        "attendance.requests",
        "projects",
    },
    "employee": {
        "home",
        "employees.internal",
        "employees.offboarding",
        "contracts.internal",
        "reimbursements.claims",
        "attendance.summary",
        "attendance.requests",
    },
    "partner": {
        "home",
        "subcontracting.notice",
        "subcontracting.quotations",
        "subcontracting.invoices",
        "subcontracting.personnel",
    },
}


def normalize_route_keys(route_keys: list[str] | set[str]) -> list[str]:
    allowed = set(UI_ROUTE_KEYS)
    return sorted({key for key in route_keys if key in allowed})


def ui_permissions_for_role(db: Session, role: str) -> list[str]:
    if role == "admin":
        return normalize_route_keys(DEFAULT_UI_PERMISSIONS["admin"])
    row = db.scalar(select(UiRolePermission).where(UiRolePermission.role == role))
    if row:
        return normalize_route_keys(row.route_keys or [])
    return normalize_route_keys(DEFAULT_UI_PERMISSIONS.get(role, set()))


def ui_permissions_for_all_roles(db: Session) -> dict[str, list[str]]:
    return {role: ui_permissions_for_role(db, role) for role in UI_ROLES}
