import asyncio
import logging
from datetime import datetime, timedelta, timezone
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from src.database import Database
from zoneinfo import ZoneInfo
from src.utils.email_service import email_service

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
        
    async def get_daily_dialogs(self) -> list:
        """
        Получение диалогов за последние 24 часа
        
        Returns
        -------
        list
            Список диалогов с информацией о пользователях
        """
        # Получаем текущее время в московской временной зоне
        moscow_tz = ZoneInfo("Europe/Moscow")
        now = datetime.now(moscow_tz)
        
        # Вычисляем время 24 часа назад
        yesterday = now - timedelta(days=1)
        
        # Конвертируем в UTC для запроса к базе данных
        yesterday_utc = yesterday.astimezone(timezone.utc)
        
        query = '''
            SELECT d.user_id, d.username, d.message, d.role, d.timestamp 
            FROM dialogs d 
            WHERE d.timestamp >= ?
            ORDER BY d.user_id, d.timestamp
        '''
        return await self.db.execute_fetch(query, (yesterday_utc.strftime('%Y-%m-%d %H:%M:%S'),))

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
        usernames = {}  # Словарь для хранения имен пользователей
        
        for dialog in dialogs:
            user_id, username, message, role, timestamp = dialog
            
            # Сохраняем username при первом появлении пользователя
            if user_id not in usernames:
                usernames[user_id] = username
            
            if current_user != user_id:
                if user_messages:
                    report += self._format_user_dialog(current_user, usernames[current_user], user_messages)
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
            report += self._format_user_dialog(current_user, usernames[current_user], user_messages)
            
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
            
            # Формируем тему письма
            subject = f'Ежедневный отчет по диалогам {datetime.now().strftime("%Y-%m-%d")}'
            
            # Отправляем отчет через email_service
            await email_service.send_email(
                subject=subject,
                body=report_html,
                recipient=None  # Будет использован notification_email из конфигурации
            )
                
            logger.info("Ежедневный отчет успешно отправлен")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного отчета: {str(e)}")

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
        
        # Добавляем задачу в планировщик с учетом московского времени
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=hour, minute=minute, timezone='Europe/Moscow'),
            id='daily_report',
            replace_existing=True
        )
        
        # Запускаем планировщик только если он еще не запущен
        if not self.scheduler.running:
            self.scheduler.start()
            
        logger.info(f"Планировщик настроен на отправку отчета в {hour:02d}:{minute:02d} (Europe/Moscow)")
            
    async def main(self):
        """Основная функция для запуска планировщика"""
        # Инициализация базы данных
        await self.db.init_db()
        
        # Для тестирования отправим отчет сразу
        logger.info("Отправка тестового отчета...")
        await self.send_daily_report()
        
        # Настройка времени отправки отчета (6:00 утра)
        self.schedule_daily_report()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(DailyReport().main())
