import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from typing import Dict, Any, Optional, List

# Локальные импорты
from src.config.config import CONFIG


class EmailService:
    """
    Сервис для отправки email уведомлений.

    Attributes
    ----------
    smtp_server : str
        SMTP сервер для отправки писем.
    smtp_port : int
        Порт SMTP сервера.
    smtp_username : str
        Имя пользователя для SMTP сервера.
    smtp_password : str
        Пароль для SMTP сервера.
    notification_email : str
        Email для отправки уведомлений.
    logger : logging.Logger
        Логгер для записи информации о работе сервиса.
    """

    def __init__(self):
        """
        Инициализация сервиса отправки email.
        """
        self.smtp_server = CONFIG.SMTP.SERVER
        self.smtp_port = CONFIG.SMTP.PORT
        self.smtp_username = CONFIG.SMTP.USERNAME
        self.smtp_password = CONFIG.SMTP.PASSWORD
        self.notification_email = CONFIG.SMTP.NOTIFICATION_EMAIL
        self.logger = logging.getLogger(__name__)

    async def send_email(self, user_id: Optional[int] = None, contact_info: Optional[Dict[str, Any]] = None, subject: Optional[str] = None, body: Optional[str] = None, recipient: Optional[str] = None) -> None:
        """
        Отправляет email с информацией о контакте пользователя или произвольным содержимым.

        Parameters
        ----------
        user_id : Optional[int], optional
            Идентификатор пользователя.
        contact_info : Optional[Dict[str, Any]], optional
            Информация о контакте пользователя.
        subject : Optional[str], optional
            Тема письма. Если не указана, будет сформирована на основе user_id.
        body : Optional[str], optional
            Содержимое письма в формате HTML. Если не указано, будет сформировано на основе contact_info.
        recipient : Optional[str], optional
            Адресат письма. Если не указан, будет использован notification_email.

        Returns
        -------
        None
        """
        try:
            # Проверяем, что указаны необходимые параметры
            if (user_id is None or contact_info is None) and (subject is None or body is None):
                self.logger.error("Недостаточно данных для отправки email")
                return

            # Логируем информацию о пользователе
            if user_id is not None:
                self.logger.info(f"Отправка email для пользователя {user_id}")
            else:
                self.logger.info("Отправка email с произвольным содержимым")
            
            # Создаем сообщение
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_username
            msg['To'] = recipient if recipient is not None else self.notification_email
            
            # Формируем тему письма
            if subject is not None:
                msg['Subject'] = subject
            elif user_id is not None:
                msg['Subject'] = f"Новая заявка от пользователя {user_id}"
            else:
                msg['Subject'] = "Уведомление"
            
            # Формируем содержимое письма
            if body is not None:
                email_body = body
            elif contact_info is not None:
                template = Template("""
                Получена новая заявка от пользователя $user_id:
                
                $contact_info
                """)
                
                # Форматируем информацию о контакте
                contact_info_str = "\n".join([f"{key}: {value}" for key, value in contact_info.items()])
                
                # Подставляем значения в шаблон
                email_body = template.substitute(user_id=user_id, contact_info=contact_info_str)
            else:
                email_body = "Содержимое письма не указано"
            
            # Добавляем текст в сообщение
            text_part = MIMEText(email_body.replace('<br>', '\n').replace('<div>', '').replace('</div>', '\n'), 'plain')
            html_part = MIMEText(email_body, 'html')
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Отправляем сообщение
            await self.send_smtp_message(msg)
                
            self.logger.info("Email успешно отправлен")
            
        except Exception as error:
            self.logger.error(f"Ошибка при отправке email: {str(error)}")
            raise

    async def send_smtp_message(self, msg: MIMEMultipart) -> None:
        """
        Отправляет сообщение через SMTP-сервер.

        Parameters
        ----------
        msg : MIMEMultipart
            Подготовленное сообщение.
        """
        try:
            async with asyncio.Lock():  # Защищаем отправку email
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._send_email(msg))
                self.logger.info("Email sent successfully")
        except Exception as e:
            self.logger.error(f"Ошибка при отправке письма: {str(e)}")
            
    def _send_email(self, msg: MIMEMultipart) -> None:
        """Внутренний метод для отправки email через SMTP"""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)

    def create_email_template(self) -> Template:
        """
        Создает шаблон письма.

        Returns
        -------
        Template
            Шаблон письма.
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
    
    def format_dialog(self, dialog_text: List[str]) -> str:
        """
        Форматирует диалог для отображения в письме.

        Parameters
        ----------
        dialog_text : list
            Список сообщений диалога.

        Returns
        -------
        str
            Отформатированный HTML-код диалога.
        """
        return ''.join(Template('<div class="message $css_class">$msg</div>').substitute(css_class=("user" if "User:" in msg else "assistant"), msg=msg) 
                      for msg in dialog_text)

    async def send_telegram_dialog_email(self, user_id: int, username: str, contact_info: Dict[str, Any], dialog_text: List[str], db=None) -> None:
        """
        Отправляет email с информацией о диалоге из Telegram и сохраняет успешный диалог в базу данных.

        Parameters
        ----------
        user_id : int
            ID пользователя.
        username : str
            Имя пользователя в Telegram.
        contact_info : dict
            Контактная информация пользователя.
        dialog_text : list
            Список сообщений диалога.
        db : Database, optional
            Объект базы данных для сохранения диалога.
        """
        if not contact_info:
            self.logger.error("Отсутствует контактная информация для отправки письма")
            return

        self.logger.info(f"Начинаем отправку письма для user_id: {user_id}, username: {username}")
        
        if not all([self.smtp_username, self.smtp_password]):
            self.logger.error("Отсутствуют SMTP-учетные данные в переменных окружения")
            return
        
        # Сохраняем успешный диалог в базу данных после получения всех данных
        if db is not None:
            try:
                await db.save_successful_dialog(
                    user_id=user_id,
                    username=username,
                    contact_info=contact_info,
                    messages=dialog_text
                )
                self.logger.info(f"Успешный диалог сохранен в базу данных для пользователя {username}")
            except Exception as e:
                self.logger.error(f"Ошибка при сохранении диалога в базу данных: {str(e)}")

        # Формируем email
        msg = MIMEMultipart('alternative')
        msg['From'] = self.smtp_username
        msg['To'] = 'da1212112@gmail.com'
        msg['Subject'] = f"Новый заказ от пользователя {username}"
        
        template = self.create_email_template()
        html_body = template.substitute(
            user_id=user_id,
            username=username,
            name=contact_info.get('name', ''),
            phone=contact_info.get('phone_number', ''),
            dialog=self.format_dialog(dialog_text)
        )

        text_part = MIMEText(html_body.replace('<br>', '\n'), 'plain')
        html_part = MIMEText(html_body, 'html')
        msg.attach(text_part)
        msg.attach(html_part)

        await self.send_smtp_message(msg)

email_service = EmailService()