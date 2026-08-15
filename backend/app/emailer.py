import smtplib
from html import escape
from email.message import EmailMessage
from .config import settings

def _html_email(subject: str, body: str) -> str:
    safe_subject = escape(subject)
    safe_body = "<br>".join(escape(line) for line in body.splitlines())
    app_url = escape(settings.frontend_url, quote=True)
    return f"""<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#15213a;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7fb;padding:28px 12px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border-radius:18px;overflow:hidden;box-shadow:0 8px 26px rgba(21,33,58,.10);">
          <tr><td style="background:#123b73;padding:24px 32px;color:#ffffff;">
            <div style="font-size:12px;font-weight:700;letter-spacing:1.8px;color:#a9d3ff;">RAJ INSTRUCTOR</div>
            <div style="font-size:22px;font-weight:700;margin-top:5px;">Drive with confidence.</div>
          </td></tr>
          <tr><td style="padding:32px;">
            <h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;color:#15213a;">{safe_subject}</h1>
            <p style="margin:0;font-size:16px;line-height:1.65;color:#3f4d65;">{safe_body}</p>
            <table role="presentation" cellspacing="0" cellpadding="0" style="margin-top:26px;"><tr>
              <td style="border-radius:9px;background:#f7b500;">
                <a href="{app_url}" style="display:inline-block;padding:13px 20px;color:#172338;text-decoration:none;font-size:15px;font-weight:700;">Open Raj Instructor</a>
              </td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:18px 32px;background:#f1f5fb;color:#66758d;font-size:12px;line-height:1.5;">
            You are receiving this because of activity in your Raj Instructor account. Please do not reply to this automated message.
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def send_email(to: str, subject: str, body: str):
    if settings.smtp_mode == "console":
        print(f"[EMAIL] to={to} subject={subject} body={body}")
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_alternative(_html_email(subject, body), subtype="html")
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST must be configured when SMTP_MODE=smtp")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
        if settings.smtp_use_tls:
            s.starttls()
        if settings.smtp_username: s.login(settings.smtp_username, settings.smtp_password)
        s.send_message(msg)
