from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from string import Template
from typing import Any, Dict, Optional, TypedDict

from openai import OpenAI, OpenAIError
from openai.types.beta.threads import Run

from bot.contact_handler import ContactHandler


class ToolOutput(TypedDict):
    """
    Структура для хранения результата выполнения инструмента.

    Attributes
    ----------
    tool_call_id : str
        Идентификатор вызова инструмента.
    output : str
        Результат выполнения инструмента в формате JSON.
    """
    tool_call_id: str
    output: str


class ChatGPTAssistant:
    """
    Класс для работы с OpenAI Assistant API.

    Parameters
    ----------
    telegram_bot : Optional[Any]
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
    contact_handler : ContactHandler
        Обработчик контактной информации.
    telegram_bot : Optional[Any]
        Экземпляр телеграм бота.
    _log_template : Template
        Шаблон для форматирования сообщений лога.
    """
    def __init__(self, telegram_bot: Optional[Any] = None) -> None:
        """
        Инициализация ассистента.

        Parameters
        ----------
        telegram_bot : Optional[Any]
            Экземпляр телеграм бота для отправки уведомлений.

        Raises
        ------
        ValueError
            Если не установлен OPENAI_ASSISTANT_ID в переменных окружения.
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(
            api_key=self.api_key,
            default_headers={
                "OpenAI-Beta": "assistants=v2"
            }
        )
        self.assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
        if self.assistant_id is None:
            raise ValueError("OPENAI_ASSISTANT_ID is not set in the environment variables.")
        
        self.logger = logging.getLogger(__name__)
        self.contact_handler = ContactHandler()
        self.telegram_bot = telegram_bot
        self._log_template = Template("$message")

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
        self.write_log(
            message=f"Creating new thread for user {user_id}"
        )
        thread = self.client.beta.threads.create()
        return thread.id

    def write_log(self, message: str) -> None:
        """
        Записывает сообщение в лог.

        Parameters
        ----------
        message : str
            Текст сообщения для записи в лог.
        """
        self.logger.info(self._log_template.substitute(message=message))

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
        self.write_log(message="Adding user message to thread")
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
        self.write_log(message="Creating run")
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

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

        Raises
        ------
        OpenAIError
            При ошибках в API OpenAI.
        """
        try:
            self.write_log(f"Getting response for message: {user_message[:50]}...")
            self.add_user_message(thread_id=thread_id, message=user_message)
            
            run = self.create_run(thread_id=thread_id)
            return await self.process_run(run=run, thread_id=thread_id, user_id=user_id)

        except OpenAIError as error:
            error_message = f"OpenAI API error: {str(error)}"
            self.logger.error(error_message)
            raise

        except Exception as error:
            error_message = f"Unexpected error: {str(error)}"
            self.logger.error(error_message)
            raise

    async def process_run(self, run: Run, thread_id: str, user_id: str) -> str:
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

        Returns
        -------
        str
            Ответ ассистента.
        """
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
                raise ValueError(f"Run failed with status: {run.status}")

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
        self.write_log(message="Run requires action (tool calls)")
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []

        for tool_call in tool_calls:
            if tool_call.function.name == "get_client_contact_info":
                tool_output = await self.process_contact_info(
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

    async def process_contact_info(
        self,
        tool_call: Any,
        user_id: str,
        thread_id: str
    ) -> ToolOutput:
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
        ToolOutput
            Результат обработки информации о контакте.
        """
        self.write_log(f"Processing get_client_contact_info for user {user_id}")
        contact_info = json.loads(tool_call.function.arguments)
        self.write_log(f"Parsed contact info: {contact_info}")

        await self.save_and_notify_contact(
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

    async def save_and_notify_contact(
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
        await self.contact_handler.store_contact_info(
            username=user_id,
            thread_id=thread_id,
            contact_info=contact_info
        )

        if self.telegram_bot is not None:
            self.write_log("TelegramBot instance found, attempting to send email")
            try:
                await self.telegram_bot.send_email(int(user_id), contact_info)
                self.write_log("Email sent successfully")
            except Exception as error:
                self.logger.error(f"Error sending email: {str(error)}")
        else:
            self.logger.error("No TelegramBot instance available")

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
        self.write_log("Run completed, retrieving assistant message")
        messages = self.client.beta.threads.messages.list(thread_id=thread_id)
        assistant_message = next(
            (msg for msg in messages.data if msg.role == "assistant"),
            None
        )

        if assistant_message is not None and assistant_message.content:
            response = assistant_message.content[0].text.value
            self.write_log(f"Got response: {response[:50]}...")
            return re.sub(r"【.*?】", "", response)
        
        raise ValueError("No assistant response found")
