from fastapi import HTTPException, status

from app.models import Employee, User


ROLE_LABELS = {
    "admin": "Admin",
    "hr": "HR",
    "pm": "PM/营业",
    "employee": "一般员工",
    "partner": "Partner",
}


MODULE_PERMISSIONS: dict[str, dict[str, set[str]]] = {
    "admin": {
        "employees": {"read", "create", "update", "delete", "import"},
        "contracts": {"read", "create", "update", "delete", "import"},
        "external_contracts": {"read", "create", "update", "delete", "generate", "upload", "download", "settle"},
        "approvals": {"read", "approve"},
        "reimbursements": {"read", "create", "update", "delete", "approve", "download"},
        "subcontracting": {"read", "create", "upload"},
        "external_personnel": {"read", "create", "update", "delete", "confirm", "download"},
        "projects": {"read", "create", "update", "delete", "recommend"},
        "attendance": {"read", "create", "update", "approve", "settings"},
    },
    "hr": {
        "employees": {"read", "update", "import"},
        "contracts": {"read", "create", "update", "delete", "import"},
        "external_contracts": set(),
        "approvals": {"read", "approve"},
        "reimbursements": {"read", "create", "update", "delete", "approve", "download"},
        "subcontracting": set(),
        "external_personnel": {"read", "update", "delete", "confirm", "download"},
        "projects": set(),
        "attendance": {"read", "create", "update", "approve"},
    },
    "pm": {
        "employees": {"read"},
        "contracts": set(),
        "external_contracts": {"read", "create", "update", "delete", "generate", "upload", "download", "settle"},
        "approvals": {"read", "approve"},
        "reimbursements": {"read_self", "create_self", "update_self", "delete_self", "download_self"},
        "subcontracting": set(),
        "external_personnel": set(),
        "projects": {"read", "create", "update", "delete", "recommend"},
        "attendance": {"read", "create"},
    },
    "employee": {
        "employees": {"read_self", "update_self"},
        "contracts": {"read_self"},
        "external_contracts": set(),
        "approvals": set(),
        "reimbursements": {"read_self", "create_self", "update_self", "delete_self", "download_self"},
        "subcontracting": set(),
        "external_personnel": set(),
        "projects": set(),
        "attendance": {"read", "create"},
    },
    "partner": {
        "employees": set(),
        "contracts": set(),
        "external_contracts": set(),
        "approvals": set(),
        "reimbursements": set(),
        "subcontracting": {"read", "create", "upload"},
        "external_personnel": {"read", "create", "download"},
        "projects": set(),
        "attendance": set(),
    },
}


def ensure_permission(user: User, module: str, action: str) -> None:
    allowed = MODULE_PERMISSIONS.get(user.role, {}).get(module, set())
    if action not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


def ensure_role(user: User, roles: set[str]) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


def can_read_employee(user: User, employee: Employee) -> bool:
    if user.role in {"admin", "hr", "pm"}:
        return True
    return user.employee_id == employee.id


def can_update_employee(user: User, employee: Employee) -> bool:
    if user.role in {"admin", "hr"}:
        return True
    return user.employee_id == employee.id
