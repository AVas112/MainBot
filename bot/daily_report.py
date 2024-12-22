import asyncio
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import Database
from telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

class DailyReport:
    def __init__(self):
        """Инициализация компонентов для ежедневного отчета"""
        self.db = Database()
        self.bot = TelegramBot()
        self.scheduler = AsyncIOScheduler()
        
    async def get_daily_dialogs(self) -> list:
        """
        Получение диалогов за последние 24 часа
        
        Returns
        -------
        list
            Список диалогов с информацией о пользователях
        """
        yesterday = datetime.now() - timedelta(days=1)
        async with self.db as db:
            query = '''
                SELECT d.user_id, d.username, d.message, d.role, d.timestamp 
                FROM dialogs d 
                WHERE d.timestamp >= ?
                ORDER BY d.user_id, d.timestamp
            '''
            return await db.execute_fetch(query, (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))

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
            msg['From'] = os.getenv('SMTP_USERNAME')
            msg['To'] = os.getenv('NOTIFICATION_EMAIL')
            
            msg.attach(MIMEText(report_html, 'html'))
            
            await self.bot.send_smtp_message(msg)
            logger.info("Ежедневный отчет успешно отправлен")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного отчета: {str(e)}")

    def schedule_daily_report(self, hour: int = 6, minute: int = 0):
        """
        Настройка расписания отправки отчета
        
        Parameters
        ----------
        hour : int
            Час отправки (по умолчанию 6)
        minute : int
            Минута отправки (по умолчанию 0)
        """
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=hour, minute=minute),
            id='daily_report',
            replace_existing=True
        )
        self.scheduler.start()
        logger.info(f"Планировщик настроен на отправку отчета в {hour:02d}:{minute:02d}")

async def main():
    """Основная функция для запуска планировщика"""
    report = DailyReport()
    # Инициализация базы данных
    await report.db.init_db()
    # Настройка времени отправки отчета (6:00 утра)
    report.schedule_daily_report()
    
    try:
        # Держим процесс работающим
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        report.scheduler.shutdown()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
