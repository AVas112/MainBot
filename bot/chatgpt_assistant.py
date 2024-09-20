import os
import logging
from openai import OpenAI

class ChatGPTAssistant:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.api_key, default_headers={"OpenAI-Beta": "assistants=v2"})
        self.assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
        if not self.assistant_id:
            raise ValueError("OPENAI_ASSISTANT_ID is not set in the environment variables.")
        self.model = "gpt-4o-mini"
        self.max_tokens = 400
        self.temperature = 0.7
        self.available_models = ["gpt-4o-mini", "gpt-4o"]
        self.thread = None
        self.logger = logging.getLogger(__name__)

    async def get_response(self, user_message: str) -> str:
        try:
            self.logger.info(f"Getting response for message: {user_message[:50]}...")
            if not self.thread:
                self.logger.info("Creating new thread")
                self.thread = self.client.beta.threads.create()
           
            self.logger.info("Adding user message to thread")
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=user_message
            )
           
            self.logger.info(f"Creating run with model {self.model}")
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=self.thread.id,
                assistant_id=self.assistant_id
            )
           
            if run.status == "requires_action":
                self.logger.info("Run requires action (tool calls)")
                # Handle tool calls here if needed
                pass
           
            if run.status == "completed":
                self.logger.info("Retrieving assistant message")
                messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
                assistant_message = next((msg for msg in messages.data if msg.role == "assistant"), None)
               
                if assistant_message and assistant_message.content:
                    response = assistant_message.content[0].text.value
                    self.logger.info(f"Got response: {response[:50]}...")
                    return response
                else:
                    raise ValueError("No assistant response found")
            else:
                raise ValueError(f"Unexpected run status: {run.status}")
       
        except Exception as e:
            error_message = f"Error while getting response from ChatGPT assistant: {str(e)}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def get_available_models(self) -> list:
        return self.available_models

    def set_max_tokens(self, max_tokens: int):
        if max_tokens > 0:
            self.max_tokens = max_tokens
            self.logger.info(f"Max tokens set to {max_tokens}")
        else:
            self.logger.warning(f"Invalid max_tokens value: {max_tokens}")
