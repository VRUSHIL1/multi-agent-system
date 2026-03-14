from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.common import settings


class EmailService:
    def __init__(self) -> None:
        self.host = settings.mail_host
        self.port = settings.mail_port
        self.username = settings.mail_username
        self.password = settings.mail_password
        self.from_address = settings.mail_from

    def send_email(self, to_address: str, subject: str, body: str, *, is_html: bool = False) -> None:
        if not self.host or not self.from_address:
            raise RuntimeError("SMTP configuration is incomplete.")

        message = EmailMessage()
        message["From"] = self.from_address
        message["To"] = to_address
        message["Subject"] = subject
        subtype = "html" if is_html else "plain"
        message.set_content(body, subtype=subtype)

        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.send_message(message)
