import secrets
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from shared.logger.logger import logger


class MocConfig:
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587
    SMTP_USER = "demonuchy@gmail.com" 
    SMTP_PASSWORD = "wwjh laes ulsf oono"

    EMAIL_FROM = "noreply@veterans.com"  # Может быть любым, даже несуществующим
    EMAIL_FROM_NAME = "Veterans Support Team"

cfg = MocConfig()

class MailService:
    def __init__(
            self, 
            host = cfg.SMTP_HOST, 
            port = cfg.SMTP_PORT, 
            username = cfg.SMTP_USER, 
            password =  cfg.SMTP_PASSWORD, 
            email_from = cfg.EMAIL_FROM, 
            name_from = cfg.EMAIL_FROM_NAME
    ):
        self.host = host
        self.port = port
        self.user = username
        self.password = password
        self.email_from = email_from
        self.name_from = name_from

    def generate_code(self) -> str:
        """Генерирует 6-значный код"""
        return ''.join(secrets.choice('0123456789') for _ in range(6))
    
    async def send_code(self, code : str, email_to : str) -> None:
        logger.debug(f"Send code, code : {code}")
        message = MIMEMultipart("alternative")
        message["From"] = f"{self.name_from} <{self.email_from}>"
        message["To"] = email_to
        message["Subject"] = "Your verification code"

        html_body = f"""
            <html>
            <body>
                <h2>Email Verification</h2>
                <p>Hello!</p>
                <p>Your verification code is:</p>
                <h1 style="color: #4CAF50; font-size: 32px;">{code}</h1>
                <p>This code will expire in <strong>5 minutes</strong>.</p>
                <p>If you didn't request this code, please ignore this email.</p>
                <br>
                <p>Best regards,<br>{self.name_from}</p>
            </body>
            </html>
            """

        html_part = MIMEText(html_body, "html")
        message.attach(html_part)

        await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                start_tls=True
            )