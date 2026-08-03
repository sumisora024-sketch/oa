import asyncio
from dataclasses import dataclass
from datetime import date
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Project
from app.services.ai import extract_project_metadata
from app.services.mail_settings import get_effective_mail_settings, test_imap_connection


@dataclass
class InboundMail:
    uid: str
    subject: str
    from_addr: str
    body: str
    attachment_text: str | None
    attachment_name: str | None


def _decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _extract_pdf_text(payload: bytes) -> str:
    reader = PdfReader(BytesIO(payload))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def _parse_message(uid: bytes, raw_message: bytes) -> InboundMail:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    body_parts: list[str] = []
    attachment_parts: list[str] = []
    attachment_names: list[str] = []

    if isinstance(message, EmailMessage):
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = part.get_content_disposition()
            content_type = part.get_content_type()
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""

            if disposition == "attachment" or filename:
                if filename:
                    attachment_names.append(filename)
                if content_type == "application/pdf":
                    attachment_parts.append(_extract_pdf_text(payload))
                elif content_type.startswith("text/"):
                    attachment_parts.append(_decode_payload(part))
                continue

            if content_type == "text/plain":
                body_parts.append(_decode_payload(part))

    body = "\n".join(part for part in body_parts if part).strip()
    if not body:
        payload = message.get_payload(decode=True)
        if payload:
            body = payload.decode(message.get_content_charset() or "utf-8", errors="replace")

    return InboundMail(
        uid=uid.decode("ascii", errors="ignore"),
        subject=str(message.get("subject") or ""),
        from_addr=str(message.get("from") or ""),
        body=body,
        attachment_text="\n\n".join(part for part in attachment_parts if part).strip() or None,
        attachment_name=", ".join(attachment_names) or None,
    )


def _fetch_unseen_messages(limit: int = 10) -> list[InboundMail]:
    settings = get_effective_mail_settings()
    if not settings.imap_enabled or not settings.imap_host or not settings.imap_username or not settings.imap_password:
        return []

    mails: list[InboundMail] = []
    import imaplib

    with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port) as client:
        client.login(settings.imap_username, settings.imap_password)
        client.select(settings.imap_folder)
        status, data = client.uid("search", None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return []

        for uid in data[0].split()[:limit]:
            status, message_data = client.uid("fetch", uid, "(BODY.PEEK[])")
            if status != "OK":
                continue
            raw_payload = next((item[1] for item in message_data if isinstance(item, tuple)), None)
            if not raw_payload:
                continue
            mails.append(_parse_message(uid, raw_payload))
            client.uid("store", uid, "+FLAGS", "(\\Seen)")
    return mails


def _parse_optional_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _save_project(db: Session, mail: InboundMail, metadata: dict[str, Any]) -> Project:
    project = Project(
        client_company=metadata["client_company"],
        project_name=metadata["project_name"],
        description=metadata["description"],
        required_skills=metadata["required_skills"],
        workplace=metadata["workplace"],
        nationality_requirement=metadata.get("nationality_requirement"),
        duration=metadata.get("duration"),
        start_date=_parse_optional_date(metadata.get("start_date")),
        end_date=_parse_optional_date(metadata.get("end_date")),
        headcount=metadata.get("headcount"),
        unit_price=metadata.get("unit_price"),
        source_email_subject=mail.subject,
        raw_email=f"From: {mail.from_addr}\n\n{mail.body}",
        attachment_name=mail.attachment_name,
        attributes={**(metadata.get("attributes") or {}), "mail_uid": mail.uid},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


async def poll_mailbox_once(limit: int = 10) -> dict[str, Any]:
    try:
        mails = await asyncio.to_thread(_fetch_unseen_messages, limit)
    except Exception as exc:
        return {"checked": 0, "imported": [], "failed": [], "error": str(exc)}
    imported: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    db = SessionLocal()
    try:
        for mail in mails:
            try:
                metadata = await extract_project_metadata(mail.subject, mail.body, mail.attachment_text)
                project = _save_project(db, mail, metadata)
                imported.append({"mail_uid": mail.uid, "project_id": project.id, "project_name": project.project_name})
            except Exception as exc:
                failed.append({"mail_uid": mail.uid, "subject": mail.subject, "error": str(exc)})
    finally:
        db.close()
    return {"checked": len(mails), "imported": imported, "failed": failed}


async def mailbox_listener_loop() -> None:
    while True:
        settings = get_effective_mail_settings()
        try:
            if not settings.enabled or not settings.imap_enabled:
                await asyncio.sleep(max(settings.poll_interval_seconds, 15))
                continue
            result = await poll_mailbox_once()
            if result.get("error"):
                print(f"[mailbox] poll failed: {result['error']}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[mailbox] poll failed: {exc}")
        await asyncio.sleep(max(settings.poll_interval_seconds, 15))
