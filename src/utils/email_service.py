import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from typing import Any

from src.config.config import CONFIG


class EmailService:
    """
    Service for sending email notifications.

    Attributes
    ----------
    smtp_server : str
        SMTP server for sending emails.
    smtp_port : int
        SMTP server port.
    smtp_username : str
        Username for the SMTP server.
    smtp_password : str
        Password for the SMTP server.
    notification_email : str
        Email address for sending notifications.
    logger : logging.Logger
        Logger for recording service operation information.
    """

    def __init__(self):
        """Initialize the email sending service."""
        self.smtp_server = CONFIG.SMTP.SERVER
        self.smtp_port = CONFIG.SMTP.PORT
        self.smtp_username = CONFIG.SMTP.USERNAME
        self.smtp_password = CONFIG.SMTP.PASSWORD
        self.notification_email = CONFIG.SMTP.NOTIFICATION_EMAIL
        self.logger = logging.getLogger(__name__)

    async def send_email(
        self,
        user_id: int | None = None,
        contact_info: dict[str, Any] | None = None,
        subject: str | None = None,
        body: str | None = None,
        recipient: str | None = None
    ) -> None:
        """
        Sends an email with user contact information or custom content.

        Parameters
        ----------
        user_id : Optional[int], optional
            User identifier.
        contact_info : Optional[Dict[str, Any]], optional
            User contact information.
        subject : Optional[str], optional
            Email subject. If not specified, will be generated based on user_id.
        body : Optional[str], optional
            Email content in HTML format. If not specified, will be generated based on contact_info.
        recipient : Optional[str], optional
            Email recipient. If not specified, notification_email will be used.

        Returns
        -------
        None
        """
        try:
            if (user_id is None or contact_info is None) and (subject is None or body is None):
                self.logger.error("Insufficient data to send email")
                return

            if user_id is not None:
                self.logger.info(f"Sending email for user {user_id}")
            else:
                self.logger.info("Sending email with custom content")
            
            msg = MIMEMultipart("alternative")
            msg["From"] = self.smtp_username
            msg["To"] = recipient if recipient is not None else self.notification_email
            
            if subject is not None:
                msg["Subject"] = subject
            elif user_id is not None:
                msg["Subject"] = f"Новая заявка от пользователя {user_id}"
            else:
                msg["Subject"] = "Уведомление"
            
            if body is not None:
                email_body = body
            elif contact_info is not None:
                template = Template("""
                Получена новая заявка от пользователя $user_id:
                
                $contact_info
                """)
                
                contact_info_str = "\n".join([f"{key}: {value}" for key, value in contact_info.items()])
                
                email_body = template.substitute(user_id=user_id, contact_info=contact_info_str)
            else:
                email_body = "Содержимое письма не указано"
            
            text_part = MIMEText(email_body.replace("<br>", "\n").replace("<div>", "").replace("</div>", "\n"), "plain")
            html_part = MIMEText(email_body, "html")
            msg.attach(text_part)
            msg.attach(html_part)
            
            await self.send_smtp_message(msg)
                
            self.logger.info("Email sent successfully") # Log in English
            
        except Exception as error:
            self.logger.error(f"Error sending email: {str(error)}") # Log in English
            raise

    async def send_smtp_message(self, msg: MIMEMultipart) -> None:
        """
        Sends a message via the SMTP server.

        Parameters
        ----------
        msg : MIMEMultipart
            Prepared message.
        """
        try:
            async with asyncio.Lock():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._send_email(msg))
                self.logger.info("Email sent successfully") # Log in English
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}") # Log in English
            
    def _send_email(self, msg: MIMEMultipart) -> None:
        """Internal method for sending email via SMTP."""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)

    def create_email_template(self) -> Template:
        """
        Creates an email template.

        Returns
        -------
        Template
            Email template.
        """
        return Template ("""
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                .section { margin: 20px 0; }
                .message { margin: 10px 0; }
                .user { color: blue; }
                .assistant { color: green; }
            </style>
        </head>
        <body>
            <div class="section">
                <h2>Заказ</h2>
                <p><strong>Клиент:</strong> $user_id ($username)</p>
                <p>Спасибо, что обратились в КлинингУМамы!</p>
                <p><strong>Имя:</strong> $name</p>
                <p><strong>Номер:</strong> $phone</p>
            </div>
            <div class="section">
                <h2>Диалог с клиентом</h2>
                $dialog
            </div>
        </body>
        </html>
        """)
    
    def format_dialog(self, dialog_text: list[str]) -> str:
        """
        Formats the dialog for display in the email.

        Parameters
        ----------
        dialog_text : list
            List of dialog messages.

        Returns
        -------
        str
            Formatted HTML code of the dialog.
        """
        return "".join(
            Template('<div class="message $css_class">$msg</div>').substitute(
                css_class=("user" if "User:" in msg else "assistant"),
                msg=msg
            )
            for msg in dialog_text
        )

    async def send_telegram_dialog_email(
        self,
        user_id: int,
        username: str,
        contact_info: dict[str, Any],
        dialog_text: list[str],
        db=None
    ) -> None:
        """
        Sends an email with dialog information from Telegram and saves the successful dialog to the database.

        Parameters
        ----------
        user_id : int
            User ID.
        username : str
            Username in Telegram.
        contact_info : dict
            User contact information.
        dialog_text : list
            List of dialog messages.
        db : Database, optional
            Database object for saving the dialog.
        """
        if not contact_info:
            self.logger.error("Missing contact information to send email") # Log in English
            return

        self.logger.info(f"Starting email sending for user_id: {user_id}, username: {username}") # Log in English
        
        if not all([self.smtp_username, self.smtp_password]):
            self.logger.error("Missing SMTP credentials in environment variables") # Log in English
            return
        
        if db is not None:
            try:
                await db.save_successful_dialog(
                    user_id=user_id,
                    username=username,
                    contact_info=contact_info,
                    messages=dialog_text
                )
                self.logger.info(f"Successful dialog saved to database for user {username}") # Log in English
            except Exception as e:
                self.logger.error(f"Error saving dialog to database: {str(e)}") # Log in English

        msg = MIMEMultipart("alternative")
        msg["From"] = self.smtp_username
        msg["To"] = "da1212112@gmail.com"
        msg["Subject"] = f"Новый заказ от пользователя {username}"
        
        template = self.create_email_template()
        html_body = template.substitute(
            user_id=user_id,
            username=username,
            name=contact_info.get("name", ""),
            phone=contact_info.get("phone_number", ""),
            dialog=self.format_dialog(dialog_text)
        )

        text_part = MIMEText(html_body.replace("<br>", "\n"), "plain")
        html_part = MIMEText(html_body, "html")
        msg.attach(text_part)
        msg.attach(html_part)

        await self.send_smtp_message(msg)

email_service = EmailService()