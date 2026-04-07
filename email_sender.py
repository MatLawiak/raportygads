"""
Moduł wysyłki raportów emailem przez SMTP.
Obsługuje Gmail (z hasłem aplikacji) i inne serwery SMTP z STARTTLS.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def send_report_email(
    recipient: str,
    subject: str,
    body: str,
    smtp_config: dict,
    filename: str = "raport.md",
) -> None:
    """
    Wysyła raport emailem jako treść wiadomości + załącznik .md.

    Args:
        recipient:   adres email odbiorcy
        subject:     temat wiadomości
        body:        treść raportu (markdown)
        smtp_config: słownik z kluczami: smtp_host, smtp_port, smtp_user, smtp_password
        filename:    nazwa pliku załącznika
    """
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = smtp_config["smtp_user"]
    msg["To"] = recipient

    # Treść jako zwykły tekst
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Załącznik .md
    attachment = MIMEBase("text", "markdown")
    attachment.set_payload(body.encode("utf-8"))
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=filename,
    )
    msg.attach(attachment)

    with smtplib.SMTP(smtp_config["smtp_host"], smtp_config["smtp_port"], timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_config["smtp_user"], smtp_config["smtp_password"])
        server.sendmail(smtp_config["smtp_user"], recipient, msg.as_string())
