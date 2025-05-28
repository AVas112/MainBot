from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ._abc import ABCBaseSettings


class TGBotConfig(ABCBaseSettings):
    BOT_TOKEN: str
    ADMIN_CHAT_ID: int

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_", env_file=".env", extra="ignore") # Возвращен env_prefix="TELEGRAM_"


class OpenAIConfig(ABCBaseSettings):
    API_KEY: str
    ASSISTANT_ID: str

    model_config = SettingsConfigDict(env_prefix="OPENAI_", env_file=".env", extra="ignore")


class ProxyConfig(ABCBaseSettings):
    USE_PROXY: bool = False
    HOST: str = ""
    PORT: int = 0
    USERNAME: str = ""
    PASSWORD: str = ""

    model_config = SettingsConfigDict(env_prefix="PROXY_", env_file=".env", extra="ignore")

    @property
    def proxy_url(self) -> str:
        """Returns the proxy URL in the format for httpx."""
        if self.USE_PROXY is False:
            return ""
        return f"http://{self.USERNAME}:{self.PASSWORD}@{self.HOST}:{self.PORT}"


class SMTPConfig(ABCBaseSettings):
    SERVER: str
    PORT: int
    USERNAME: str
    PASSWORD: str
    NOTIFICATION_EMAIL: str

    model_config = SettingsConfigDict(env_prefix="SMTP_", env_file=".env", extra="ignore")


class WebUIConfig(ABCBaseSettings):
    BASE_URL: str

    model_config = SettingsConfigDict(env_prefix="WEB_UI_", env_file=".env", extra="ignore")


class ReminderConfig(ABCBaseSettings):
    # Время в минутах для отправки первого напоминания
    FIRST_REMINDER_TIME: int = Field(default=1)
    # Время в минутах для отправки второго напоминания
    SECOND_REMINDER_TIME: int = Field(default=2)
    # Промпт для первого напоминания
    FIRST_REMINDER_PROMPT: str = Field(
        default=(
            "Напиши текст, просто текст без свои комменатриев:"
            "Привет! Как вы? Решили, как будете двигаться с продажами? Место пока ещё есть, могу забронировать для вас. "
        )
    )
    # Промпт для второго напоминания
    SECOND_REMINDER_PROMPT: str = Field(
        default=(
            "Пользователь не отвечает уже какое то время. Напиши ему более настойчивое сообщение с предложением "
            "продолжить диалог. Используй контекст предыдущего общения. Предложи ему скидку в 20% на любой "
            "тип уборки при необходимости."
        )
    )
    # Включена ли система напоминаний
    ENABLED: bool = Field(default=True)
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Config:
    TELEGRAM = TGBotConfig()
    OPENAI = OpenAIConfig()
    PROXY = ProxyConfig()
    SMTP = SMTPConfig()
    WEB_UI = WebUIConfig()
    REMINDER = ReminderConfig()


CONFIG = Config()
