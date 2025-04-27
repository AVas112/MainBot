from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from openai import OpenAI, OpenAIError
from openai.types.beta.threads import Run

from src.config.config import CONFIG
from src.utils.email_service import email_service
from src.utils.proxy import create_proxy_client
from src.telegram_notifications import notify_admin_about_successful_dialog

if TYPE_CHECKING:
    from src.telegram_bot import TelegramBot

class ChatGPTAssistant:
    """
    Class for interacting with the OpenAI Assistant API.

    Parameters
    ----------
    telegram_bot : Optional['TelegramBot']
        Telegram bot instance for sending notifications.

    Attributes
    ----------
    api_key : str
        OpenAI API key.
    client : OpenAI
        OpenAI API client.
    assistant_id : str
        OpenAI assistant ID.
    logger : logging.Logger
        Logger for recording information about the assistant's operation.
    telegram_bot : Optional['TelegramBot']
        Telegram bot instance.
    """

    def __init__(self, telegram_bot: TelegramBot | None = None) -> None:
        """
        Assistant initialization.

        Parameters
        ----------
        telegram_bot : Optional['TelegramBot']
            Telegram bot instance for sending notifications.

        Raises
        ------
        ValueError
            If OPENAI_ASSISTANT_ID is not set in environment variables.
        """
        http_client = create_proxy_client()
        self.assistant_id = CONFIG.OPENAI.ASSISTANT_ID
        self.api_key = CONFIG.OPENAI.API_KEY
        self.telegram_bot = telegram_bot
        
        openai_params = {"api_key": self.api_key, "default_headers": {"OpenAI-Beta": "assistants=v2"}}
        if http_client is not None:
            openai_params["http_client"] = http_client
            
        self.client = OpenAI(**openai_params)
        self.logger = logging.getLogger(__name__)

    def create_thread(self, user_id: str) -> str:
        """
        Creates a new thread for communication with the user.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        str
            Identifier of the created thread.
        """
        self.logger.info(f"Creating new thread for user {user_id}")
        thread = self.client.beta.threads.create()
        return thread.id

    async def get_response(self, user_message: str, thread_id: str, user_id: str) -> str:
        """
        Gets a response from the assistant to the user's message.

        Parameters
        ----------
        user_message : str
            User message.
        thread_id : str
            Thread identifier.
        user_id : str
            User identifier.

        Returns
        -------
        str
            Assistant's response.
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
        Adds the user's message to the thread.

        Parameters
        ----------
        thread_id : str
            Thread identifier.
        message : str
            Text of the user's message.
        """
        self.logger.info("Adding user message to thread")
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )

    def create_run(self, thread_id: str) -> Run:
        """
        Creates a new run to process messages in the thread.

        Parameters
        ----------
        thread_id : str
            Thread identifier.

        Returns
        -------
        Run
            Run object.
        """
        self.logger.info("Creating run")
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

    async def process_run(self, run: Run, thread_id: str, user_id: str, retry_count: int = 0) -> str:
        """
        Processes the run to get a response from the assistant.

        Parameters
        ----------
        run : Run
            Run object.
        thread_id : str
            Thread identifier.
        user_id : str
            User identifier.
        retry_count : int
            Current number of retry attempts.

        Returns
        -------
        str
            Assistant's response.
        """
        max_retries = 3
        
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
                self.logger.warning(
                    f"Run failed for user {user_id} with status: {run.status}. "
                    f"Attempt {retry_count + 1} of {max_retries}"
                )
                
                if retry_count < max_retries:
                    new_run = self.create_run(thread_id)
                    return await self.process_run(new_run, thread_id, user_id, retry_count + 1)
                else:
                    self.logger.error(f"Max retries ({max_retries}) reached for user {user_id}")
                    return await self.get_assistant_response(thread_id=thread_id)

            await asyncio.sleep(1)

    async def get_assistant_response(self, thread_id: str) -> str:
        """
        Gets the response from the assistant.

        Parameters
        ----------
        thread_id : str
            Thread identifier.

        Returns
        -------
        str
            Assistant's response.
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

            response = re.sub(r"【.*?】", "", response)

            response = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", response)

            response = re.sub(
                r"\[([^]]+)]\(([^)]+)\)",
                r'<a href="\2">\1</a>',
                response
            )

            return response

        return "Sorry, failed to get a response. Please try again."

    async def handle_required_action(self, run: Run, thread_id: str, user_id: str) -> Run:
        """
        Handles the required actions for the run.

        Parameters
        ----------
        run : Run
            Run object.
        thread_id : str
            Thread identifier.
        user_id : str
            User identifier.

        Returns
        -------
        Run
            Run object after handling required actions.
        """
        self.logger.info("Run requires action (tool calls)")
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []

        for tool_call in tool_calls:
            if tool_call.function.name == "get_client_contact_info":
                tool_output = await self.process_contact_info_tool_call(
                    tool_call=tool_call,
                    user_id=user_id
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
        user_id: str
    ) -> dict[str, str]:
        """
        Processes the user's contact information.

        Parameters
        ----------
        tool_call : Any
            Tool call to get contact information.
        user_id : str
            User identifier.

        Returns
        -------
        Dict[str, str]
            Result of processing contact information.
        """
        self.logger.info(f"Processing get_client_contact_info for user {user_id}")
        contact_info = json.loads(tool_call.function.arguments)
        self.logger.info(f"Parsed contact info: {contact_info}")

        await self.send_contact_notification(
            user_id=user_id,
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
        contact_info: dict[str, Any]
    ) -> None:
        """
        Saves contact information and sends a notification.

        Parameters
        ----------
        user_id : str
            User identifier.
        contact_info : Dict[str, Any]
            Contact information.
        """
        self.logger.info("Attempting to send email notification")
        try:
            int_user_id = int(user_id)
            if int_user_id in self.telegram_bot.usernames:
                username = self.telegram_bot.usernames[int_user_id]
            else:
                self.logger.info("User has hidden their Telegram username")
                username = str(user_id)
            
            dialog_text = await self.telegram_bot.db.get_dialog(int_user_id)
            
            await email_service.send_telegram_dialog_email(
                user_id=int_user_id,
                username=username,
                contact_info=contact_info,
                dialog_text=dialog_text,
                db=self.telegram_bot.db if self.telegram_bot is not None and hasattr(self.telegram_bot, "db") else None
            )
            self.logger.info("Email sent successfully")
            await notify_admin_about_successful_dialog(
                bot=self.telegram_bot.bot,
                user_id=int_user_id,
                username=username,
                contact_info=contact_info
            )
            self.logger.info("Admin notified about successful dialog")
        except Exception as error:
            self.logger.error(f"Error sending email or telegram notification: {str(error)}")
