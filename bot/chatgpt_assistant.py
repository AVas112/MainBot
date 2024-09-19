import os
from openai import OpenAI

class ChatGPTAssistant:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.api_key, default_headers={"OpenAI-Beta": "assistants=v2"})
        self.assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
        if not self.assistant_id:
            raise ValueError("OPENAI_ASSISTANT_ID is not set in the environment variables.")
        self.model = "gpt-4o-mini"
        self.max_tokens = 800
        self.temperature = 0.7
        self.available_models = ["gpt-4o-mini", "gpt-4o"]
        self.thread = None

    async def get_response(self, user_message: str) -> str:
        try:
            if not self.thread:
                self.thread = self.client.beta.threads.create()
           
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=user_message
            )
           
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant_id,
                instructions=f"You are using the {self.model} model. Respond within {self.max_tokens} tokens."
            )
           
            while run.status != "completed":
                run = self.client.beta.threads.runs.retrieve(thread_id=self.thread.id, run_id=run.id)
           
            messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
            assistant_message = next((msg for msg in messages.data if msg.role == "assistant"), None)
           
            if assistant_message and assistant_message.content:
                return assistant_message.content[0].text.value
            else:
                raise ValueError("No assistant response found")
       
        except Exception as e:
            error_message = f"Error while getting response from ChatGPT assistant: {str(e)}"
            raise Exception(error_message)

    def get_available_models(self) -> list:
        return self.available_models

    def set_max_tokens(self, max_tokens: int):
        if max_tokens > 0:
            self.max_tokens = max_tokens

    def set_model(self, model: str):
        if model in self.available_models:
            self.model = model
        else:
            raise ValueError(f"Invalid model. Available models are: {', '.join(self.available_models)}")
