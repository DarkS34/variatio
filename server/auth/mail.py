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

from .. import installation


def send(to: str, subject: str, body: str) -> bool:
    """Send the message, or log it whole when there is no SMTP.

    False means it was only logged, which is what lets the API hand the link back in its
    own response instead of promising a mail that never left.
    """
    if not configured():
        logger.info(f"Correo no enviado (SMTP sin configurar) para {to}: {subject}\n{body}")
        return False

    message = EmailMessage()
    message["From"] = installation.MAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        _deliver(message)
    except Exception as exc:  # noqa: BLE001 - a mail failure must not fail the request
        logger.error(f"No se pudo enviar el correo a {to}: {type(exc).__name__}: {exc}")
        return False
    return True


def configured() -> bool:
    """True when an SMTP host is set.

    `GET /api/auth/me` reports this as `mail_configured`, which is what makes "Mi perfil"
    hide the address field where nothing could deliver to it.
    """
    return bool(installation.smtp_host())


def _deliver(message: EmailMessage) -> None:
    """Open the connection the settings describe and hand one message over."""
    host, port = installation.smtp_host(), installation.SMTP_PORT
    context = ssl.create_default_context()
    if installation.SMTP_SSL:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as client:
            _authenticate(client)
            client.send_message(message)
        return
    with smtplib.SMTP(host, port, timeout=20) as client:
        if installation.SMTP_STARTTLS:
            client.starttls(context=context)
        _authenticate(client)
        client.send_message(message)


def _authenticate(client: smtplib.SMTP) -> None:
    """Log in, when a user is configured."""
    if installation.SMTP_USER:
        client.login(installation.SMTP_USER, installation.SMTP_PASSWORD)
