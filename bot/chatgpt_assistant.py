import os
import re
import logging
import json
from openai import OpenAI
from bot.contact_handler import ContactHandler

class ChatGPTAssistant:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.api_key, default_headers={"OpenAI-Beta": "assistants=v2"})
        self.assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
        if not self.assistant_id:
            raise ValueError("OPENAI_ASSISTANT_ID is not set in the environment variables.")
        self.logger = logging.getLogger(__name__)
        self.contact_handler = ContactHandler()

    def create_thread(self, user_id: str):
        self.logger.info(f"Creating new thread for user {user_id}")
        thread = self.client.beta.threads.create()
        return thread.id

    async def get_response(self, user_message: str, thread_id: str) -> str:
        try:
            self.logger.info(f"Getting response for message: {user_message[:50]}...")

            self.logger.info("Adding user message to thread")
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_message
            )

            self.logger.info(f"Creating run")
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )

            if run.status == "requires_action":
                self.logger.info("Run requires action (tool calls)")
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                
                for tool_call in tool_calls:
                    if tool_call.function.name == "get_client_contact_info":
                        # Обработка полученной контактной информации
                        contact_info = json.loads(tool_call.function.arguments)
                        # Сохраняем информацию в файл
                        await self.contact_handler.save_contact_info(
                            username=user_id,  # Используем user_id как username
                            thread_id=thread_id,
                            contact_info=contact_info
                        )
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"status": "success", "message": "Contact information saved"})
                        })

                # Отправляем результаты обработки функций обратно
                if tool_outputs:
                    run = self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )

            if run.status == "completed":
                self.logger.info("Retrieving assistant message")
                messages = self.client.beta.threads.messages.list(thread_id=thread_id)
                assistant_message = next((msg for msg in messages.data if msg.role == "assistant"), None)

                if assistant_message and assistant_message.content:
                    response = assistant_message.content[0].text.value
                    self.logger.info(f"Got response: {response[:50]}...")

                    # Удаление любых текстов между символами 【 и 】 включительно
                    response = re.sub(r"【.*?】", "", response)
                    
                    return response
                else:
                    raise ValueError("No assistant response found")
            else:
                raise ValueError(f"Unexpected run status: {run.status}")

        except Exception as e:
            error_message = f"Error while getting response from ChatGPT assistant: {str(e)}"
            self.logger.error(error_message)
            raise Exception(error_message)
