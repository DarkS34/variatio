"""How an invitation or a reset link reaches a person.

With no SMTP configured the link is written to the log instead of being sent, and the
API says so in its response. That is not a stub: for a closed group the administrator
issuing the invitation is usually the one who will paste the link into a message, and a
deployment that silently swallowed the mail would be worse than one that hands it back.
"""

import smtplib
import ssl
from email.message import EmailMessage

from loguru import logger

from .. import settings


def configured() -> bool:
    return bool(settings.smtp_host())


def send(to: str, subject: str, body: str) -> bool:
    """True when the message left the process; False when it was only logged."""
    if not configured():
        logger.info(f"Correo no enviado (SMTP sin configurar) para {to}: {subject}\n{body}")
        return False

    message = EmailMessage()
    message["From"] = settings.MAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        _deliver(message)
    except Exception as exc:  # noqa: BLE001 - a mail failure must not fail the request
        logger.error(f"No se pudo enviar el correo a {to}: {type(exc).__name__}: {exc}")
        return False
    return True


def _deliver(message: EmailMessage) -> None:
    host, port = settings.smtp_host(), settings.SMTP_PORT
    context = ssl.create_default_context()
    if settings.SMTP_SSL:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as client:
            _authenticate(client)
            client.send_message(message)
        return
    with smtplib.SMTP(host, port, timeout=20) as client:
        if settings.SMTP_STARTTLS:
            client.starttls(context=context)
        _authenticate(client)
        client.send_message(message)


def _authenticate(client: smtplib.SMTP) -> None:
    if settings.SMTP_USER:
        client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
