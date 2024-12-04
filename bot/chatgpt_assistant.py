from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from string import Template
from typing import Any, Dict, Optional, TypedDict

from openai import OpenAI
from openai.types.beta.threads import Run

from bot.contact_handler import ContactHandler


class ToolOutput(TypedDict):
    tool_call_id: str
    output: str


class ChatGPTAssistant:
    def __init__(self, telegram_bot: Optional[Any] = None) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(
            api_key=self.api_key,
            default_headers={"OpenAI-Beta": "assistants=v2"}
        )
        self.assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
        if self.assistant_id is None:
            raise ValueError("OPENAI_ASSISTANT_ID is not set in the environment variables.")
        
        self.logger = logging.getLogger(__name__)
        self.contact_handler = ContactHandler()
        self.telegram_bot = telegram_bot
        self._log_template = Template("$message")

    def create_thread(self, user_id: str) -> str:
        self.logger.info(
            self._log_template.substitute(message=f"Creating new thread for user {user_id}")
        )
        thread = self.client.beta.threads.create()
        return thread.id

    async def get_response(self, user_message: str, thread_id: str, user_id: str) -> str:
        try:
            self._log_message(f"Getting response for message: {user_message[:50]}...")
            self._add_user_message(thread_id=thread_id, message=user_message)
            
            run = self._create_run(thread_id=thread_id)
            return await self._process_run(run=run, thread_id=thread_id, user_id=user_id)

        except Exception as error:
            error_message = f"Error while getting response from ChatGPT assistant: {str(error)}"
            self.logger.error(error_message)
            raise

    def _log_message(self, message: str) -> None:
        self.logger.info(self._log_template.substitute(message=message))

    def _add_user_message(self, thread_id: str, message: str) -> None:
        self._log_message("Adding user message to thread")
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )

    def _create_run(self, thread_id: str) -> Run:
        self._log_message("Creating run")
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

    async def _process_run(self, run: Run, thread_id: str, user_id: str) -> str:
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run.status == "requires_action":
                run = await self._handle_required_action(run=run, thread_id=thread_id, user_id=user_id)
                continue

            if run.status == "completed":
                return await self._get_assistant_response(thread_id=thread_id)

            if run.status in ["failed", "cancelled", "expired"]:
                raise ValueError(f"Run failed with status: {run.status}")

            await asyncio.sleep(1)

    async def _handle_required_action(self, run: Run, thread_id: str, user_id: str) -> Run:
        self._log_message("Run requires action (tool calls)")
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []

        for tool_call in tool_calls:
            if tool_call.function.name == "get_client_contact_info":
                tool_output = await self._process_contact_info(
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

    async def _process_contact_info(
        self,
        tool_call: Any,
        user_id: str,
        thread_id: str
    ) -> ToolOutput:
        self._log_message(f"Processing get_client_contact_info for user {user_id}")
        contact_info = json.loads(tool_call.function.arguments)
        self._log_message(f"Parsed contact info: {contact_info}")

        await self._save_and_notify_contact(
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

    async def _save_and_notify_contact(
        self,
        user_id: str,
        thread_id: str,
        contact_info: Dict[str, Any]
    ) -> None:
        await self.contact_handler.save_contact_info(
            username=user_id,
            thread_id=thread_id,
            contact_info=contact_info
        )

        if self.telegram_bot is not None:
            self._log_message("TelegramBot instance found, attempting to send email")
            try:
                self.telegram_bot.send_email(user_id, contact_info)
                self._log_message("Email sent successfully")
            except Exception as error:
                self.logger.error(f"Error sending email: {str(error)}")
        else:
            self.logger.error("No TelegramBot instance available")

    async def _get_assistant_response(self, thread_id: str) -> str:
        self._log_message("Run completed, retrieving assistant message")
        messages = self.client.beta.threads.messages.list(thread_id=thread_id)
        assistant_message = next(
            (msg for msg in messages.data if msg.role == "assistant"),
            None
        )

        if assistant_message is not None and assistant_message.content:
            response = assistant_message.content[0].text.value
            self._log_message(f"Got response: {response[:50]}...")
            return re.sub(r"【.*?】", "", response)
        
        raise ValueError("No assistant response found")
