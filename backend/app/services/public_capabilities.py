from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentAccessPolicy, NotificationRule, WorkflowDefinition


ROLE_CODES = ["admin", "soumu", "hr", "pm", "employee", "partner"]
NOTIFICATION_CHANNELS = ["in_app", "email"]

EVENT_DEFAULTS = {
    "contract.expiring": {
        "display_name": "契約期限通知",
        "channels": ["in_app", "email"],
        "recipient_roles": ["soumu", "admin"],
        "include_related": True,
        "schedule": {"days_before": [30, 14, 7, 1], "send_time": "09:00"},
    },
    "workflow.submitted": {
        "display_name": "承認依頼通知",
        "channels": ["in_app", "email"],
        "recipient_roles": [],
        "include_related": True,
        "schedule": {},
    },
    "profile.change_submitted": {
        "display_name": "個人情報変更申請",
        "channels": ["in_app", "email"],
        "recipient_roles": ["soumu"],
        "include_related": True,
        "schedule": {},
    },
}

WORKFLOW_DEFAULTS = {
    "partner_quotation": ("パートナー見積書承認", [{"kind": "role", "roles": ["pm", "soumu", "hr"]}]),
    "partner_invoice": ("パートナー請求書承認", [{"kind": "role", "roles": ["soumu", "hr"]}]),
    "reimbursement": ("経費承認", [{"kind": "role", "roles": ["soumu", "hr"]}]),
    "employee_offboarding": (
        "退職承認",
        [
            {"kind": "role", "roles": ["pm"], "label": "所属責任者確認"},
            {"kind": "role", "roles": ["soumu", "hr"], "label": "総務確認"},
        ],
    ),
    "employee_profile_change": ("個人情報変更承認", [{"kind": "role", "roles": ["soumu", "hr"]}]),
}

DOCUMENT_POLICY_DEFAULTS = {
    "purchase_order": ("発注書", ["admin", "soumu", "pm"], False, True),
    "quotation": ("見積書", ["admin", "soumu", "pm"], False, True),
    "invoice": ("請求書", ["admin", "soumu", "pm"], False, True),
    "uploaded_contract": ("契約書", ["admin", "soumu", "hr", "pm"], False, True),
    "partner_quotation": ("パートナー見積書", ["admin", "soumu", "hr", "pm", "partner"], True, True),
    "partner_invoice": ("パートナー請求書", ["admin", "soumu", "hr", "partner"], True, True),
    "reimbursement": ("経費証憑", ["admin", "soumu", "hr"], True, False),
    "resume": ("履歴書", ["admin", "soumu", "hr", "pm", "partner"], True, True),
    "avatar": ("顔写真", ["admin", "soumu", "hr", "pm", "partner"], True, True),
    "timesheet": ("勤務表", ["admin", "soumu", "hr", "pm", "partner"], True, True),
    "residence_card": ("在留カード", ["admin", "soumu", "hr"], True, False),
    "my_number": ("マイナンバー", ["admin", "soumu", "hr"], True, False),
    "tax": ("税務書類", ["admin", "soumu", "hr"], True, False),
    "other": ("その他", ["admin", "soumu", "hr"], True, False),
}


def ensure_public_capability_defaults(db: Session) -> None:
    for event_code, values in EVENT_DEFAULTS.items():
        if not db.scalar(select(NotificationRule).where(NotificationRule.event_code == event_code)):
            db.add(NotificationRule(event_code=event_code, enabled=True, recipient_user_ids=[], **values))

    for workflow_type, (display_name, steps) in WORKFLOW_DEFAULTS.items():
        if not db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.workflow_type == workflow_type)):
            db.add(
                WorkflowDefinition(
                    workflow_type=workflow_type,
                    display_name=display_name,
                    enabled=True,
                    steps=steps,
                    version=1,
                )
            )

    for document_type, (display_name, roles, owner_access, related_access) in DOCUMENT_POLICY_DEFAULTS.items():
        if not db.scalar(select(DocumentAccessPolicy).where(DocumentAccessPolicy.document_type == document_type)):
            db.add(
                DocumentAccessPolicy(
                    document_type=document_type,
                    display_name=display_name,
                    allowed_roles=roles,
                    owner_access=owner_access,
                    related_access=related_access,
                )
            )
