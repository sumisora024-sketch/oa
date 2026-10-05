from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentAccessPolicy, DocumentArchive, User


def can_access_archive(db: Session, user: User, row: DocumentArchive) -> bool:
    if user.role == "admin":
        return True
    policy = db.scalar(select(DocumentAccessPolicy).where(DocumentAccessPolicy.document_type == row.document_type))
    if not policy:
        return False
    if user.role in set(policy.allowed_roles or []):
        return True
    if policy.owner_access:
        if user.employee and row.employee_name and user.employee.full_name == row.employee_name:
            return True
        if user.partner and row.partner_name and user.partner.company_name == row.partner_name:
            return True
    if policy.related_access:
        attrs = row.attributes or {}
        related_user_ids = {int(value) for value in attrs.get("related_user_ids", []) if str(value).isdigit()}
        return user.id in related_user_ids
    return False
