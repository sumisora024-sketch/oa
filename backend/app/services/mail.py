from email.message import EmailMessage

from app.services.mail_settings import get_effective_mail_settings, smtp_client


def send_mail(to: str, subject: str, body: str) -> bool:
    settings = get_effective_mail_settings()
    if not settings.smtp_enabled or not settings.smtp_host:
        print(f"[mail-dev] To: {to}\nSubject: {subject}\n{body}")
        return False

    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_username or "noreply@example.com"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtp_client(settings) as smtp:
        smtp.send_message(message)
    return True
