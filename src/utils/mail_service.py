import secrets
import aiosmtplib
from string import Template
from pathlib import Path
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

    def _load_mail_template(self, template_dir : str, file_name : str):
        current_file = Path(__file__)  # /app/src/utils/mail_service.py
        logger.debug(f"Curent file {current_file}")
        project_root = current_file.parent.parent  # /app/src/
        logger.debug(f"project_root {project_root}")
        template_path = project_root / template_dir / file_name
        logger.debug(f"template path {template_path}")
        if not template_path.exists():
            logger.error(f"Template file not found: {template_path}")   
            raise 
        html_template = template_path.read_text(encoding="utf-8")
        return html_template
    
    async def send_code(self, code : str, email_to : str) -> None:
        try:
            logger.debug(f"Send code, code : {code}")
            message = MIMEMultipart("alternative")
            message["From"] = f"{self.name_from} <{self.email_from}>"
            message["To"] = email_to
            message["Subject"] = "Your verification code"

            html_template = self._load_mail_template("templates", "email_template.html")
            template = Template(html_template)
            html_body = template.safe_substitute(code=code, name_from=self.name_from)
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
        except Exception as e:
            logger.warn(f"Send mail notification failed : {e}")
        