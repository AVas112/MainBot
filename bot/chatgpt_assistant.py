import os
from openai import OpenAI

class ChatGPTAssistant:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.api_key)
        self.assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
        self.model = "gpt-4o-mini"
        self.max_tokens = 150
        self.temperature = 0.7
        self.available_models = ["gpt-4o-mini", "gpt-4o"]

    async def get_response(self, user_message: str) -> str:
        """
        Send a message to ChatGPT assistant and get the response.
        
        :param user_message: The user's input message
        :return: ChatGPT's response as a string
        """
        try:
            thread = self.client.beta.threads.create()
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_message
            )
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id,
                instructions=f"You are using the {self.model} model. Respond within {self.max_tokens} tokens."
            )

            # Wait for the run to complete
            while run.status != "completed":
                run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

            # Get the assistant's response
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            assistant_message = next(msg for msg in messages if msg.role == "assistant")
            return assistant_message.content[0].text.value

        except Exception as e:
            raise Exception(f"Error while getting response from ChatGPT assistant: {e}")

    def update_settings(self, model: str = None, max_tokens: int = None, temperature: float = None):
        """
        Update the ChatGPT API request parameters.
        
        :param model: The model to use for chat completion
        :param max_tokens: The maximum number of tokens to generate
        :param temperature: The sampling temperature to use
        """
        if model and model in self.available_models:
            self.model = model
        if max_tokens is not None:
            self.max_tokens = max_tokens
        if temperature is not None:
            self.temperature = temperature

    def get_available_models(self) -> list:
        """
        Get the list of available models.
        
        :return: List of available model names
        """
        return self.available_models

    def set_max_tokens(self, max_tokens: int):
        """
        Set the maximum number of tokens for the response.

        :param max_tokens: The maximum number of tokens to generate
        """
        if max_tokens > 0:
            self.max_tokens = max_tokens
