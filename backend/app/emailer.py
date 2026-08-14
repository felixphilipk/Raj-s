import smtplib
from email.message import EmailMessage
from .config import settings

def send_email(to: str, subject: str, body: str):
    if settings.smtp_mode == "console":
        print(f"[EMAIL] to={to} subject={subject} body={body}")
        return
    msg = EmailMessage(); msg["From"] = settings.smtp_from; msg["To"] = to; msg["Subject"] = subject; msg.set_content(body)
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST must be configured when SMTP_MODE=smtp")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
        if settings.smtp_use_tls:
            s.starttls()
        if settings.smtp_username: s.login(settings.smtp_username, settings.smtp_password)
        s.send_message(msg)
