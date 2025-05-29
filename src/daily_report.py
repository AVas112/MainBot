import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.database import Database
from src.utils.email_service import email_service


logger = logging.getLogger(__name__)

class DailyReport:
    def __init__(self, telegram_bot=None):
        """
        Initialize components for the daily report.
        
        Parameters
        ----------
        telegram_bot : TelegramBot, optional
            Existing TelegramBot instance
        """
        self.db = Database()
        self.bot = telegram_bot
        self.scheduler = AsyncIOScheduler()
        
    async def get_daily_dialogs(self) -> list:
        """
        Get dialogs from the last 24 hours.
        
        Returns
        -------
        list
            List of dialogs with user information
        """
        moscow_tz = ZoneInfo("Europe/Moscow")
        now = datetime.now(moscow_tz)
        
        yesterday = now - timedelta(days=1)
        
        yesterday_utc = yesterday.astimezone(timezone.utc)
        
        query = """
            SELECT d.user_id, d.username, d.message, d.role, d.timestamp 
            FROM dialogs d 
            WHERE d.timestamp >= ?
            ORDER BY d.user_id, d.timestamp
        """
        return await self.db.execute_fetch(query, (yesterday_utc.strftime("%Y-%m-%d %H:%M:%S"),))

    def format_report(self, dialogs: list) -> str:
        """
        Format dialogs for the report.
        
        Parameters
        ----------
        dialogs : list
            List of dialogs from the database
            
        Returns
        -------
        str
            Formatted HTML report
        """
        if not dialogs:
            return "<p>За последние 24 часа диалогов не было.</p>"
            
        report = "<h2>Отчет по диалогам за последние 24 часа</h2>"
        
        user_dialogs = {} 
        
        for dialog_row in dialogs:
            user_id, username, message, role, timestamp_str = dialog_row
            
            if user_id not in user_dialogs:
                user_dialogs[user_id] = {"username": username, "messages": []}
            
            user_dialogs[user_id]["username"] = username 
            
            if isinstance(timestamp_str, str):
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            else: 
                timestamp = timestamp_str
                
            user_dialogs[user_id]["messages"].append({
                "role": role,
                "message": message,
                "timestamp": timestamp
            })
            
        for user_id, data in user_dialogs.items():
            sorted_messages = sorted(data["messages"], key=lambda x: x["timestamp"])
            report += self._format_user_dialog(user_id, data["username"], sorted_messages)
            
        return report

    def _format_user_dialog(self, user_id: int, username: str, messages: list) -> str:
        """
        Format the dialog of a single user.
        
        Parameters
        ----------
        user_id : int
            User ID
        username : str
            Username
        messages : list
            List of user messages
            
        Returns
        -------
        str
            Formatted HTML user dialog
        """
        dialog = f"<h3>Диалог с пользователем: {username} (ID: {user_id})</h3><div class='dialog'>"
        
        for msg in messages:
            role = "Пользователь" if msg["role"] == "user" else "Бот"
            time = msg["timestamp"].strftime("%H:%M:%S")
            dialog += f"<p><strong>{role} [{time}]:</strong> {msg['message']}</p>"
            
        dialog += "</div><hr>"
        return dialog

    async def send_daily_report(self):
        """Send the daily report via email."""
        try:
            dialogs = await self.get_daily_dialogs()
            report_html = self.format_report(dialogs)
            
            subject = f'Ежедневный отчет по диалогам {datetime.now().strftime("%Y-%m-%d")}'
            
            await email_service.send_email(
                subject=subject,
                body=report_html,
                recipient=None
            )
                
            logger.info("Daily report sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending daily report: {str(e)}")

    def schedule_daily_report(self, hour: int = None, minute: int = None):
        """
        Configure the report sending schedule.
        
        Parameters
        ----------
        hour : int, optional
            Sending hour (default from REPORT_HOUR in .env or 6)
        minute : int, optional
            Sending minute (default from REPORT_MINUTE in .env or 0)
        """
        hour = hour or int(os.getenv("REPORT_HOUR", "6"))
        minute = minute or int(os.getenv("REPORT_MINUTE", "0"))
        
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=hour, minute=minute, timezone="Europe/Moscow"),
            id="daily_report",
            replace_existing=True
        )
        
        if not self.scheduler.running:
            self.scheduler.start()
            
        logger.info(f"Scheduler configured to send report at {hour:02d}:{minute:02d} (Europe/Moscow)")
            
    async def main(self):
        """Main function to run the scheduler."""
        await self.db.init_db()
        
        logger.info("Sending test report...")
        await self.send_daily_report()
        
        self.schedule_daily_report()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(DailyReport().main())
