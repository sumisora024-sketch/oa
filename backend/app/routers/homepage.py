from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.core.permissions import MODULE_PERMISSIONS
from app.core.ui_permissions import ui_permissions_for_role
from app.db import get_db
from app.deps import get_current_user
from app.models import BusinessPartner, Contract, Employee, ExternalDocument, ExternalPersonnel, Project, ProjectAssignment, User
from app.schemas import HomepageOut
from app.services.salary import current_contract_for_employee, ensure_salary_record, salary_record_out

router = APIRouter(prefix="/homepage", tags=["homepage"])


NIT_COMPANY_PROFILE = {
    "company_name": "日本インフォテック株式会社",
    "english_name": "NIHON INFO TEC CO.,LTD",
    "url": "https://www.nit-g.co.jp/",
    "phone": "03-6863-5619",
    "email": "eigyo@nit-g.co.jp",
    "address": "〒108-0075 東京都港区港南2-16-4 品川グランドセントラルタワー8階",
    "services": [
        {"title": "受託開発", "description": "お客様の構想に合わせたシステム構成から導入まで支援します。"},
        {"title": "SES事業", "description": "システム開発に必要な人材と技術をリアルタイムに提供します。"},
        {"title": "オフショア開発", "description": "提案から納品導入まで幅広い工程をサポートします。"},
        {"title": "システム保守", "description": "日本で運営するシステムに安心な保守サービスを提供します。"},
        {"title": "BPO事業", "description": "業務効率化、コスト削減、リスク管理を支援します。"},
        {"title": "システム構築サービス", "description": "豊富なノウハウを活かし最適な方式で構築します。"},
    ],
}


@router.get("", response_model=HomepageOut)
def homepage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    employee = db.get(Employee, user.employee_id) if user.employee_id else None
    if employee and employee.is_deleted:
        employee = None
    partner = db.get(BusinessPartner, user.partner_id) if user.partner_id else None
    contracts = []
    projects = []
    current_contract = None
    salary = None
    company_profile = NIT_COMPANY_PROFILE if user.role == "partner" else None
    if employee:
        contracts = list(
            db.scalars(
                select(Contract).where(Contract.employee_id == employee.id, Contract.is_deleted.is_(False))
            ).all()
        )
        current_contract = current_contract_for_employee(db, employee.id)
        salary_record = ensure_salary_record(db, employee)
        if salary_record:
            db.commit()
            db.refresh(salary_record)
            salary = salary_record_out(salary_record)
        projects = list(
            db.scalars(
                select(Project)
                .join(ProjectAssignment)
                .where(ProjectAssignment.employee_id == employee.id, ProjectAssignment.status == "assigned")
                .order_by(Project.created_at.desc())
            ).all()
        )
    if partner:
        partner.attributes = {
            **(partner.attributes or {}),
            "quotation_count": len(
                list(
                    db.scalars(
                        select(ExternalDocument.id).where(
                            ExternalDocument.partner_id == partner.id,
                            ExternalDocument.document_type == "partner_quotation",
                        )
                    ).all()
                )
            ),
            "personnel_count": len(
                list(db.scalars(select(ExternalPersonnel.id).where(ExternalPersonnel.partner_id == partner.id)).all())
            ),
        }
    permissions = {module: sorted(actions) for module, actions in MODULE_PERMISSIONS.get(user.role, {}).items()}
    return {
        "user": user,
        "employee": employee,
        "partner": partner,
        "company_profile": company_profile,
        "current_contract": current_contract,
        "contracts": contracts,
        "projects": projects,
        "salary": salary,
        "permissions": permissions,
        "ui_permissions": ui_permissions_for_role(db, user.role),
    }
