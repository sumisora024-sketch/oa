from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import ensure_role
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import MailSettingsIn, MailSettingsOut, MailTestOut
from app.services.mail_settings import (
    get_public_mail_settings,
    save_mail_settings,
    test_imap_connection,
    test_smtp_connection,
)

router = APIRouter(prefix="/mail-settings", tags=["mail-settings"])


@router.get("", response_model=MailSettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    return get_public_mail_settings(db)


@router.put("", response_model=MailSettingsOut)
def update_settings(payload: MailSettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    return save_mail_settings(db, payload)


@router.post("/test-imap", response_model=MailTestOut)
def test_imap(user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    try:
        ok, message = test_imap_connection()
        return {"ok": ok, "message": message}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


@router.post("/test-smtp", response_model=MailTestOut)
def test_smtp(user: User = Depends(get_current_user)):
    ensure_role(user, {"admin"})
    try:
        ok, message = test_smtp_connection()
        return {"ok": ok, "message": message}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
