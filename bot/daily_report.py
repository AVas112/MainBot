import asyncio
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import smtplib
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot.database import Database

logger = logging.getLogger(__name__)

class DailyReport:
    def __init__(self, telegram_bot=None):
        """
        Инициализация компонентов для ежедневного отчета
        
        Parameters
        ----------
        telegram_bot : TelegramBot, optional
            Существующий экземпляр TelegramBot
        """
        self.db = Database()
        self.bot = telegram_bot
        self.scheduler = AsyncIOScheduler()
        
        # Если бот не передан, инициализируем базовые SMTP настройки
        if not telegram_bot:
            self.smtp_server = os.getenv('SMTP_SERVER')
            self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
            self.smtp_username = os.getenv('SMTP_USERNAME')
            self.smtp_password = os.getenv('SMTP_PASSWORD')
            self.notification_email = os.getenv('NOTIFICATION_EMAIL')
            
    async def get_daily_dialogs(self) -> list:
        """
        Получение диалогов за последние 24 часа
        
        Returns
        -------
        list
            Список диалогов с информацией о пользователях
        """
        yesterday = datetime.now() - timedelta(days=1)
        query = '''
            SELECT d.user_id, d.username, d.message, d.role, d.timestamp 
            FROM dialogs d 
            WHERE d.timestamp >= ?
            ORDER BY d.user_id, d.timestamp
        '''
        return await self.db.execute_fetch(query, (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))

    def format_report(self, dialogs: list) -> str:
        """
        Форматирование диалогов для отчета
        
        Parameters
        ----------
        dialogs : list
            Список диалогов из базы данных
            
        Returns
        -------
        str
            Отформатированный HTML-отчет
        """
        if not dialogs:
            return "<p>За последние 24 часа диалогов не было.</p>"
            
        report = "<h2>Отчет по диалогам за последние 24 часа</h2>"
        current_user = None
        user_messages = []
        
        for dialog in dialogs:
            user_id, username, message, role, timestamp = dialog
            
            if current_user != user_id:
                if user_messages:
                    report += self._format_user_dialog(current_user, username, user_messages)
                current_user = user_id
                user_messages = []
            
            # Преобразуем timestamp в объект datetime, если это строка
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                
            user_messages.append({
                'role': role,
                'message': message,
                'timestamp': timestamp
            })
            
        if user_messages:
            report += self._format_user_dialog(current_user, username, user_messages)
            
        return report

    def _format_user_dialog(self, user_id: int, username: str, messages: list) -> str:
        """
        Форматирование диалога одного пользователя
        
        Parameters
        ----------
        user_id : int
            ID пользователя
        username : str
            Имя пользователя
        messages : list
            Список сообщений пользователя
            
        Returns
        -------
        str
            Отформатированный HTML-диалог пользователя
        """
        dialog = f"<h3>Диалог с пользователем: {username} (ID: {user_id})</h3><div class='dialog'>"
        
        for msg in messages:
            role = "Пользователь" if msg['role'] == 'user' else "Бот"
            time = msg['timestamp'].strftime('%H:%M:%S')
            dialog += f"<p><strong>{role} [{time}]:</strong> {msg['message']}</p>"
            
        dialog += "</div><hr>"
        return dialog

    async def send_daily_report(self):
        """Отправка ежедневного отчета на email"""
        try:
            dialogs = await self.get_daily_dialogs()
            report_html = self.format_report(dialogs)
            
            msg = MIMEMultipart()
            msg['Subject'] = f'Ежедневный отчет по диалогам {datetime.now().strftime("%Y-%m-%d")}'
            msg['From'] = self.smtp_username if not self.bot else self.bot.smtp_username
            msg['To'] = self.notification_email if not self.bot else self.bot.notification_email
            
            msg.attach(MIMEText(report_html, 'html'))
            
            if self.bot:
                await self.bot.send_smtp_message(msg)
            else:
                # Создаем временный event loop для отправки email если нет бота
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._send_email(msg))
                
            logger.info("Ежедневный отчет успешно отправлен")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного отчета: {str(e)}")

    def _send_email(self, msg):
        """Внутренний метод для отправки email через SMTP"""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
        except Exception as e:
            logger.error(f"Ошибка при отправке письма: {str(e)}")

    def schedule_daily_report(self, hour: int = None, minute: int = None):
        """
        Настройка расписания отправки отчета
        
        Parameters
        ----------
        hour : int, optional
            Час отправки (по умолчанию из REPORT_HOUR в .env или 6)
        minute : int, optional
            Минута отправки (по умолчанию из REPORT_MINUTE в .env или 0)
        """
        # Получаем значения из переменных окружения или используем значения по умолчанию
        hour = hour or int(os.getenv('REPORT_HOUR', '6'))
        minute = minute or int(os.getenv('REPORT_MINUTE', '0'))
        
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=hour, minute=minute),
            id='daily_report',
            replace_existing=True
        )
        self.scheduler.start()
        logger.info(f"Планировщик настроен на отправку отчета в {hour:02d}:{minute:02d}")

    async def main(self):
        """Основная функция для запуска планировщика"""
        # Инициализация базы данных
        await self.db.init_db()
        
        # Для тестирования отправим отчет сразу
        logger.info("Отправка тестового отчета...")
        await self.send_daily_report()
        
        # Настройка времени отправки отчета (6:00 утра)
        self.schedule_daily_report()
        
        try:
            # Держим процесс работающим
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.scheduler.shutdown()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(DailyReport().main())
