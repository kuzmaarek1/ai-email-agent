import os
from email.message import EmailMessage

import aiosmtplib

SMTP_HOST = os.getenv("SMTP_HOST", "mailhog")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@example.com")


async def send_email(to_address: str, reply_to: str, subject: str, body: str) -> None:
    """
    Wysyła wiadomość e-mail przez SMTP (MailHog) do wskazanego działu.

    Args:
        to_address: adres e-mail działu docelowego (np. it@example.com)
        reply_to: adres e-mail pierwotnego nadawcy zgłoszenia
        subject: temat wiadomości
        body: treść wiadomości
    """
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to_address
    message["Reply-To"] = reply_to
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
    )
