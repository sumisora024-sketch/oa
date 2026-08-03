import base64
import hashlib
import imaplib
import smtplib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import MailSettings
from app.schemas import MailSettingsIn, MailSettingsOut


@dataclass
class EffectiveMailSettings:
    provider: str
    enabled: bool
    imap_enabled: bool
    imap_host: str | None
    imap_port: int
    imap_username: str | None
    imap_password: str | None
    imap_folder: str
    poll_interval_seconds: int
    smtp_enabled: bool
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_from: str | None
    smtp_use_tls: bool


def _fernet() -> Fernet:
    settings = get_settings()
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None


def _env_settings() -> EffectiveMailSettings:
    settings = get_settings()
    return EffectiveMailSettings(
        provider="env",
        enabled=settings.mailbox_poll_enabled or bool(settings.smtp_host),
        imap_enabled=settings.mailbox_poll_enabled,
        imap_host=settings.mailbox_imap_host or None,
        imap_port=993,
        imap_username=settings.mailbox_imap_username or None,
        imap_password=settings.mailbox_imap_password or None,
        imap_folder=settings.mailbox_imap_folder,
        poll_interval_seconds=settings.mailbox_poll_interval_seconds,
        smtp_enabled=bool(settings.smtp_host),
        smtp_host=settings.smtp_host or None,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username or None,
        smtp_password=settings.smtp_password or None,
        smtp_from=settings.smtp_from or settings.smtp_username or None,
        smtp_use_tls=settings.smtp_use_tls,
    )


def get_mail_settings_row(db: Session) -> MailSettings:
    row = db.get(MailSettings, 1)
    if not row:
        row = MailSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _public_from_effective(config: EffectiveMailSettings) -> MailSettingsOut:
    return MailSettingsOut(
        provider=config.provider,
        enabled=config.enabled,
        imap_enabled=config.imap_enabled,
        imap_host=config.imap_host,
        imap_port=config.imap_port,
        imap_username=config.imap_username,
        has_imap_password=bool(config.imap_password),
        imap_folder=config.imap_folder,
        poll_interval_seconds=config.poll_interval_seconds,
        smtp_enabled=config.smtp_enabled,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_username=config.smtp_username,
        has_smtp_password=bool(config.smtp_password),
        smtp_from=config.smtp_from,
        smtp_use_tls=config.smtp_use_tls,
    )


def get_public_mail_settings(db: Session) -> MailSettingsOut:
    row = db.get(MailSettings, 1)
    if not row:
        return _public_from_effective(_env_settings())
    return MailSettingsOut(
        provider=row.provider,
        enabled=row.enabled,
        imap_enabled=row.imap_enabled,
        imap_host=row.imap_host,
        imap_port=row.imap_port,
        imap_username=row.imap_username,
        has_imap_password=bool(row.imap_password_encrypted),
        imap_folder=row.imap_folder,
        poll_interval_seconds=row.poll_interval_seconds,
        smtp_enabled=row.smtp_enabled,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_username=row.smtp_username,
        has_smtp_password=bool(row.smtp_password_encrypted),
        smtp_from=row.smtp_from,
        smtp_use_tls=row.smtp_use_tls,
    )


def save_mail_settings(db: Session, payload: MailSettingsIn) -> MailSettingsOut:
    row = get_mail_settings_row(db)
    provider = payload.provider
    row.provider = provider
    row.enabled = payload.enabled and provider != "disabled"
    row.imap_enabled = payload.imap_enabled
    row.imap_host = payload.imap_host
    row.imap_port = payload.imap_port
    row.imap_username = payload.imap_username
    row.imap_folder = payload.imap_folder or "INBOX"
    row.poll_interval_seconds = max(payload.poll_interval_seconds, 15)
    row.smtp_enabled = payload.smtp_enabled
    row.smtp_host = payload.smtp_host
    row.smtp_port = payload.smtp_port
    row.smtp_username = payload.smtp_username
    row.smtp_from = str(payload.smtp_from) if payload.smtp_from else None
    row.smtp_use_tls = payload.smtp_use_tls

    if provider == "disabled":
        row.enabled = False
        row.imap_enabled = False
        row.smtp_enabled = False
    elif provider == "gmail_app_password":
        row.enabled = True
        row.imap_enabled = True
        row.smtp_enabled = True
        row.imap_host = row.imap_host or "imap.gmail.com"
        row.imap_port = row.imap_port or 993
        row.smtp_host = row.smtp_host or "smtp.gmail.com"
        row.smtp_port = row.smtp_port or 587
        row.smtp_use_tls = True
    elif provider == "smtp_only":
        row.enabled = True
        row.imap_enabled = False
        row.smtp_enabled = True
    elif provider == "generic_imap_smtp":
        row.enabled = True
        row.imap_enabled = payload.imap_enabled
        row.smtp_enabled = payload.smtp_enabled

    if payload.imap_password is not None:
        row.imap_password_encrypted = encrypt_secret(payload.imap_password)
    if payload.smtp_password is not None:
        row.smtp_password_encrypted = encrypt_secret(payload.smtp_password)
    db.commit()
    db.refresh(row)
    return get_public_mail_settings(db)


def get_effective_mail_settings() -> EffectiveMailSettings:
    db = SessionLocal()
    try:
        row = db.get(MailSettings, 1)
        if row:
            return EffectiveMailSettings(
                provider=row.provider,
                enabled=row.enabled,
                imap_enabled=row.imap_enabled,
                imap_host=row.imap_host,
                imap_port=row.imap_port,
                imap_username=row.imap_username,
                imap_password=decrypt_secret(row.imap_password_encrypted),
                imap_folder=row.imap_folder,
                poll_interval_seconds=row.poll_interval_seconds,
                smtp_enabled=row.smtp_enabled,
                smtp_host=row.smtp_host,
                smtp_port=row.smtp_port,
                smtp_username=row.smtp_username,
                smtp_password=decrypt_secret(row.smtp_password_encrypted),
                smtp_from=row.smtp_from,
                smtp_use_tls=row.smtp_use_tls,
            )
        return _env_settings()
    finally:
        db.close()


@contextmanager
def smtp_client(config: EffectiveMailSettings | None = None) -> Iterator[smtplib.SMTP]:
    config = config or get_effective_mail_settings()
    if not config.smtp_enabled or not config.smtp_host:
        raise ValueError("SMTP is not configured")
    if config.smtp_port == 465 and not config.smtp_use_tls:
        with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15) as smtp:
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password or "")
            yield smtp
        return
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
        smtp.ehlo()
        if config.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        if config.smtp_username:
            smtp.login(config.smtp_username, config.smtp_password or "")
        yield smtp


def test_imap_connection(config: EffectiveMailSettings | None = None) -> tuple[bool, str]:
    config = config or get_effective_mail_settings()
    if not config.imap_enabled or not config.imap_host or not config.imap_username or not config.imap_password:
        return False, "IMAP is not configured"
    with imaplib.IMAP4_SSL(config.imap_host, config.imap_port) as client:
        client.login(config.imap_username, config.imap_password)
        status, _ = client.select(config.imap_folder)
        if status != "OK":
            return False, f"Cannot open mailbox folder: {config.imap_folder}"
    return True, "IMAP connection succeeded"


def test_smtp_connection(config: EffectiveMailSettings | None = None) -> tuple[bool, str]:
    config = config or get_effective_mail_settings()
    if not config.smtp_enabled or not config.smtp_host:
        return False, "SMTP is not configured"
    with smtp_client(config) as smtp:
        smtp.noop()
    return True, "SMTP connection succeeded"
