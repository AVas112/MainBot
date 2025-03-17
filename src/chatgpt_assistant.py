from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional, TYPE_CHECKING

from openai import OpenAI, OpenAIError
from openai.types.beta.threads import Run

from src.config.config import CONFIG
from src.utils.proxy import create_proxy_client
from src.utils.email_service import email_service

# Используем TYPE_CHECKING для избежания циклических импортов
if TYPE_CHECKING:
    from src.telegram_bot import TelegramBot

class ChatGPTAssistant:
    """
    Класс для работы с OpenAI Assistant API.

    Parameters
    ----------
    telegram_bot : Optional['TelegramBot']
        Экземпляр телеграм бота для отправки уведомлений.

    Attributes
    ----------
    api_key : str
        Ключ API OpenAI.
    client : OpenAI
        Клиент OpenAI API.
    assistant_id : str
        Идентификатор ассистента OpenAI.
    logger : logging.Logger
        Логгер для записи информации о работе ассистента.
    telegram_bot : Optional['TelegramBot']
        Экземпляр телеграм бота.
    """
    def __init__(self, telegram_bot: Optional['TelegramBot'] = None) -> None:
        """
        Инициализация ассистента.

        Parameters
        ----------
        telegram_bot : Optional['TelegramBot']
            Экземпляр телеграм бота для отправки уведомлений.

        Raises
        ------
        ValueError
            Если не установлен OPENAI_ASSISTANT_ID в переменных окружения.
        """
        http_client = create_proxy_client()
        self.assistant_id = CONFIG.OPENAI.ASSISTANT_ID
        self.api_key = CONFIG.OPENAI.API_KEY
        self.telegram_bot = telegram_bot
        
        # Создаем клиент OpenAI с прокси или без
        openai_params = {"api_key": self.api_key, "default_headers": {"OpenAI-Beta": "assistants=v2"}}
        if http_client is not None:
            openai_params["http_client"] = http_client
            
        self.client = OpenAI(**openai_params)
        self.logger = logging.getLogger(__name__)

    def create_thread(self, user_id: str) -> str:
        """
        Создает новый поток для общения с пользователем.

        Parameters
        ----------
        user_id : str
            Идентификатор пользователя.

        Returns
        -------
        str
            Идентификатор созданного потока.
        """
        self.logger.info(f"Creating new thread for user {user_id}")
        thread = self.client.beta.threads.create()
        return thread.id

    async def get_response(self, user_message: str, thread_id: str, user_id: str) -> str:
        """
        Получает ответ от ассистента на сообщение пользователя.

        Parameters
        ----------
        user_message : str
            Сообщение пользователя.
        thread_id : str
            Идентификатор потока.
        user_id : str
            Идентификатор пользователя.

        Returns
        -------
        str
            Ответ ассистента.
        """
        try:
            self.logger.info(f"Getting response for message: {user_message[:50]}...")
            self.add_user_message(thread_id=thread_id, message=user_message)
            
            run = self.create_run(thread_id=thread_id)
            return await self.process_run(run=run, thread_id=thread_id, user_id=user_id, retry_count=0)

        except OpenAIError as error:
            self.logger.error(f"OpenAI API error: {str(error)}")
            raise

        except Exception as error:
            self.logger.error(f"Unexpected error: {str(error)}")
            raise

    def add_user_message(self, thread_id: str, message: str) -> None:
        """
        Добавляет сообщение пользователя в поток.

        Parameters
        ----------
        thread_id : str
            Идентификатор потока.
        message : str
            Текст сообщения пользователя.
        """
        self.logger.info("Adding user message to thread")
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )

    def create_run(self, thread_id: str) -> Run:
        """
        Создает новый запуск для обработки сообщений в потоке.

        Parameters
        ----------
        thread_id : str
            Идентификатор потока.

        Returns
        -------
        Run
            Объект запуска.
        """
        self.logger.info("Creating run")
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

    async def process_run(self, run: Run, thread_id: str, user_id: str, retry_count: int = 0) -> str:
        """
        Обрабатывает запуск для получения ответа от ассистента.

        Parameters
        ----------
        run : Run
            Объект запуска.
        thread_id : str
            Идентификатор потока.
        user_id : str
            Идентификатор пользователя.
        retry_count : int
            Текущее количество попыток повторной отправки.

        Returns
        -------
        str
            Ответ ассистента.
        """
        max_retries = 3  # Максимальное количество попыток
        
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run.status == "requires_action":
                run = await self.handle_required_action(run=run, thread_id=thread_id, user_id=user_id)
                continue

            if run.status == "completed":
                return await self.get_assistant_response(thread_id=thread_id)

            if run.status in ["failed", "cancelled", "expired"]:
                self.logger.warning(f"Run failed for user {user_id} with status: {run.status}. Attempt {retry_count + 1} of {max_retries}")
                
                if retry_count < max_retries:
                    new_run = self.create_run(thread_id)
                    return await self.process_run(new_run, thread_id, user_id, retry_count + 1)
                else:
                    self.logger.error(f"Max retries ({max_retries}) reached for user {user_id}")
                    return await self.get_assistant_response(thread_id=thread_id)

            await asyncio.sleep(1)

    async def handle_required_action(self, run: Run, thread_id: str, user_id: str) -> Run:
        """
        Обрабатывает необходимые действия для запуска.

        Parameters
        ----------
        run : Run
            Объект запуска.
        thread_id : str
            Идентификатор потока.
        user_id : str
            Идентификатор пользователя.

        Returns
        -------
        Run
            Объект запуска после обработки необходимых действий.
        """
        self.logger.info("Run requires action (tool calls)")
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []

        for tool_call in tool_calls:
            if tool_call.function.name == "get_client_contact_info":
                tool_output = await self.process_contact_info_tool_call(
                    tool_call=tool_call,
                    user_id=user_id,
                    thread_id=thread_id
                )
                tool_outputs.append(tool_output)

        return self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs
        )

    async def process_contact_info_tool_call(
        self,
        tool_call: Any,
        user_id: str,
        thread_id: str
    ) -> Dict[str, str]:
        """
        Обрабатывает информацию о контакте пользователя.

        Parameters
        ----------
        tool_call : Any
            Вызов инструмента для получения информации о контакте.
        user_id : str
            Идентификатор пользователя.
        thread_id : str
            Идентификатор потока.

        Returns
        -------
        Dict[str, str]
            Результат обработки информации о контакте.
        """
        self.logger.info(f"Processing get_client_contact_info for user {user_id}")
        contact_info = json.loads(tool_call.function.arguments)
        self.logger.info(f"Parsed contact info: {contact_info}")

        await self.send_contact_notification(
            user_id=user_id,
            thread_id=thread_id,
            contact_info=contact_info
        )

        return {
            "tool_call_id": tool_call.id,
            "output": json.dumps({
                "status": "success",
                "message": "Contact information saved and notification sent"
            })
        }

    async def send_contact_notification(
        self,
        user_id: str,
        thread_id: str,
        contact_info: Dict[str, Any]
    ) -> None:
        """
        Сохраняет информацию о контакте и отправляет уведомление.

        Parameters
        ----------
        user_id : str
            Идентификатор пользователя.
        thread_id : str
            Идентификатор потока.
        contact_info : Dict[str, Any]
            Информация о контакте.
        """
        self.logger.info("Attempting to send email notification")
        try:
            # Получаем имя пользователя из телеграм-бота
            int_user_id = int(user_id)
            if int_user_id in self.telegram_bot.usernames:
                username = self.telegram_bot.usernames[int_user_id]
            else:
                self.logger.info("Пользователь скрыл свое телеграм имя")
                username = str(user_id)
            
            dialog_text = await self.telegram_bot.db.get_dialog(int_user_id)
            
            # Отправляем email через синглтон email_service
            await email_service.send_telegram_dialog_email(
                user_id=int_user_id,
                username=username,
                contact_info=contact_info,
                dialog_text=dialog_text,
                db=self.telegram_bot.db if self.telegram_bot is not None and hasattr(self.telegram_bot, 'db') else None
            )
            self.logger.info("Email sent successfully")
        except Exception as error:
            self.logger.error(f"Error sending email: {str(error)}")

    async def get_assistant_response(self, thread_id: str) -> str:
        """
        Получает ответ от ассистента.

        Parameters
        ----------
        thread_id : str
            Идентификатор потока.

        Returns
        -------
        str
            Ответ ассистента.
        """
        self.logger.info("Run completed, retrieving assistant message")
        messages = self.client.beta.threads.messages.list(thread_id=thread_id)
        assistant_message = next(
            (msg for msg in messages.data if msg.role == "assistant"),
            None
        )

        if assistant_message is not None and assistant_message.content:
            response = assistant_message.content[0].text.value
            self.logger.info(f"Got response: {response[:50]}...")
            
            # Удаляем специальные маркеры
            response = re.sub(r"【.*?】", "", response)
            
            # Преобразуем двойные звездочки в HTML-теги для жирного текста
            response = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", response)
            
            # Преобразуем Markdown-ссылки в HTML-формат для Telegram
            response = re.sub(
                r"\[([^\]]+)\]\(([^\)]+)\)",
                r'<a href="\2">\1</a>',
                response
            )
            
            return response
        
        return "Извините, не удалось получить ответ. Пожалуйста, попробуйте еще раз."
