import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Optional

from src.config.config import CONFIG


if TYPE_CHECKING:
    from src.chatgpt_assistant import ChatGPTAssistant
    from src.database import Database
    from src.telegram_bot import TelegramBot


class ReminderService:
    """
    Сервис для отправки автоматических напоминаний неактивным пользователям.
    
    Отслеживает активность пользователей и отправляет напоминания через
    заданные промежутки времени с использованием ChatGPT для генерации
    персонализированных сообщений.
    
    Parameters
    ----------
    telegram_bot : TelegramBot
        Экземпляр Telegram бота для отправки сообщений
    db : Database
        Экземпляр базы данных для отслеживания активности пользователей
    chatgpt_assistant : ChatGPTAssistant
        Экземпляр ассистента ChatGPT для генерации сообщений
    
    Attributes
    ----------
    logger : logging.Logger
        Логгер для записи информации о работе сервиса
    telegram_bot : TelegramBot
        Экземпляр Telegram бота
    db : Database
        Экземпляр базы данных
    chatgpt_assistant : ChatGPTAssistant
        Экземпляр ассистента ChatGPT
    is_running : bool
        Флаг, указывающий, запущен ли сервис
    check_interval : int
        Интервал проверки неактивных пользователей в секундах
    """
    
    def __init__(
        self,
        telegram_bot: "TelegramBot",
        db: "Database",
        chatgpt_assistant: "ChatGPTAssistant"
    ) -> None:
        """
        Инициализация сервиса напоминаний.
        
        Parameters
        ----------
        telegram_bot : TelegramBot
            Экземпляр Telegram бота для отправки сообщений
        db : Database
            Экземпляр базы данных для отслеживания активности пользователей
        chatgpt_assistant : ChatGPTAssistant
            Экземпляр ассистента ChatGPT для генерации сообщений
        """
        self.logger = logging.getLogger(__name__)
        self.telegram_bot = telegram_bot
        self.db = db
        self.chatgpt_assistant = chatgpt_assistant
        self.is_running = False
        self.check_interval = 60  # Проверка каждую минуту
        self.task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """
        Запускает сервис напоминаний.
        
        Создает фоновую задачу для периодической проверки неактивных пользователей
        и отправки им напоминаний.
        """
        if not CONFIG.REMINDER.ENABLED:
            self.logger.info("Сервис напоминаний отключен в настройках")
            return
            
        if self.is_running:
            self.logger.warning("Сервис напоминаний уже запущен")
            return
            
        self.is_running = True
        self.logger.info("Запуск сервиса напоминаний")
        self.task = asyncio.create_task(self._check_inactive_users_loop())
        
    async def stop(self) -> None:
        """
        Останавливает сервис напоминаний.
        
        Отменяет фоновую задачу проверки неактивных пользователей.
        """
        if not self.is_running or self.task is None:
            return
            
        self.is_running = False
        self.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.task
        self.logger.info("Сервис напоминаний остановлен")
    
    async def _check_inactive_users_loop(self) -> None:
        """
        Основной цикл проверки неактивных пользователей.
        
        Периодически проверяет наличие неактивных пользователей и отправляет
        им напоминания в соответствии с настройками.
        """
        self.logger.info("Запущен цикл проверки неактивных пользователей")
        while self.is_running:
            try:
                await self._check_and_send_reminders()
            except Exception as e:
                self.logger.error(f"Ошибка при проверке неактивных пользователей: {e}")
                
            await asyncio.sleep(self.check_interval)
    
    async def _check_and_send_reminders(self) -> None:
        """
        Проверяет неактивных пользователей и отправляет им напоминания.
        
        Получает списки пользователей для первого и второго напоминания
        и отправляет им соответствующие сообщения.
        """
        # Проверка пользователей для первого напоминания
        first_reminder_time = CONFIG.REMINDER.FIRST_REMINDER_TIME
        users_for_first_reminder = await self.db.get_users_for_first_reminder(
            minutes=first_reminder_time
        )
        
        for user_id in users_for_first_reminder:
            # Проверяем, не успешен ли диалог
            is_successful = await self.db.is_successful_dialog(user_id=user_id)
            if is_successful:
                self.logger.info(f"Пользователь {user_id} имеет успешный диалог, напоминание не отправляется")
                continue
                
            await self._send_reminder(
                user_id=user_id,
                reminder_type="first",
                inactive_minutes=first_reminder_time
            )
            await self.db.mark_first_reminder_sent(user_id=user_id)
        
        # Проверка пользователей для второго напоминания
        second_reminder_time = CONFIG.REMINDER.SECOND_REMINDER_TIME
        users_for_second_reminder = await self.db.get_users_for_second_reminder(
            minutes=second_reminder_time
        )
        
        for user_id in users_for_second_reminder:
            # Проверяем, не успешен ли диалог
            is_successful = await self.db.is_successful_dialog(user_id=user_id)
            if is_successful:
                self.logger.info(f"Пользователь {user_id} имеет успешный диалог, напоминание не отправляется")
                continue
                
            await self._send_reminder(
                user_id=user_id,
                reminder_type="second",
                inactive_minutes=second_reminder_time
            )
            await self.db.mark_second_reminder_sent(user_id=user_id)
    
    async def _send_reminder(self, user_id: int, reminder_type: str, inactive_minutes: int) -> None:
        """
        Отправляет напоминание пользователю.
        
        Parameters
        ----------
        user_id : int
            ID пользователя
        reminder_type : str
            Тип напоминания ("first" или "second")
        inactive_minutes : int
            Время неактивности пользователя в минутах
        """
        try:
            # Получаем thread_id для пользователя
            thread_id = self.telegram_bot.threads.get(str(user_id))
            if thread_id is None:
                self.logger.warning(f"Не найден thread_id для пользователя {user_id}")
                return
                
            # Формируем промпт для ChatGPT в зависимости от типа напоминания
            if reminder_type == "first":
                prompt_template = CONFIG.REMINDER.FIRST_REMINDER_PROMPT
            else:
                prompt_template = CONFIG.REMINDER.SECOND_REMINDER_PROMPT
                
            prompt = prompt_template.format(minutes=inactive_minutes)
            
            # Получаем ответ от ChatGPT
            self.logger.info(f"Отправка запроса к ChatGPT для напоминания пользователю {user_id}")
            response = await self.chatgpt_assistant.get_response(
                user_message=prompt,
                thread_id=thread_id,
                user_id=str(user_id)
            )
            
            # Отправляем сообщение пользователю
            self.logger.info(f"Отправка напоминания пользователю {user_id}")
            await self.telegram_bot.bot.send_message(
                chat_id=user_id,
                text=response,
                parse_mode="HTML"
            )
            
            # Сохраняем сообщение в базу данных
            username = self.telegram_bot.usernames.get(user_id, str(user_id))
            await self.db.save_message(
                user_id=user_id,
                username=username,
                message=response,
                role="assistant"
            )
            
            self.logger.info(f"Напоминание успешно отправлено пользователю {user_id}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")
