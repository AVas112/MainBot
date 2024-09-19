import os
from openai import OpenAI

class ChatGPTAssistant:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"
        self.max_tokens = 150
        self.temperature = 0.7
        self.available_models = ["gpt-4o-mini", "gpt-4o"]

    def get_response(self, user_message: str) -> str:
        """
        Send a message to ChatGPT and get the response.
        
        :param user_message: The user's input message
        :return: ChatGPT's response as a string
        """
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": user_message}],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            raise Exception(f"Error while getting response from ChatGPT: {e}")

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
