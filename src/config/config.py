from pydantic_settings import SettingsConfigDict

from ._abc import ABCBaseSettings


class TGBotConfig(ABCBaseSettings):
    BOT_TOKEN: str
    ADMIN_CHAT_ID: int

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")


class OpenAIConfig(ABCBaseSettings):
    API_KEY: str
    ASSISTANT_ID: str

    model_config = SettingsConfigDict(env_prefix="OPENAI_")


class ProxyConfig(ABCBaseSettings):
    USE_PROXY: bool = False
    HOST: str = ""
    PORT: int = 0
    USERNAME: str = ""
    PASSWORD: str = ""

    model_config = SettingsConfigDict(env_prefix="PROXY_")

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

    model_config = SettingsConfigDict(env_prefix="SMTP_")


class WebUIConfig(ABCBaseSettings):
    BASE_URL: str

    model_config = SettingsConfigDict(env_prefix="WEB_UI_")


class ReminderConfig(ABCBaseSettings):
    # Время в минутах для отправки первого напоминания
    FIRST_REMINDER_TIME: int = 1
    # Время в минутах для отправки второго напоминания
    SECOND_REMINDER_TIME: int = 2
    # Промпт для первого напоминания
    FIRST_REMINDER_PROMPT: str = (
        "Пользователь не отвечает уже {minutes} минут. Напиши ему короткое сообщение, чтобы вернуть его в диалог. "
        "Используй контекст предыдущего общения. Используй информацию об услугах из CliningInfo.txt. "
        "Используй все навыки продаж для этого."
    )
    # Промпт для второго напоминания
    SECOND_REMINDER_PROMPT: str = (
        "Пользователь не отвечает уже {minutes} минут. Напиши ему более настойчивое сообщение с предложением "
        "продолжить диалог. Используй контекст предыдущего общения. Предложи ему скидку в 20% на любой "
        "тип уборки при необходимости."
    )
    # Включена ли система напоминаний
    ENABLED: bool = True
    
    model_config = SettingsConfigDict(env_prefix="REMINDER_")


class ReportConfig(ABCBaseSettings):
    HOUR: int = 8
    MINUTE: int = 0

    model_config = SettingsConfigDict(env_prefix="REPORT_")


class Config:
    TELEGRAM = TGBotConfig()
    OPENAI = OpenAIConfig()
    PROXY = ProxyConfig()
    SMTP = SMTPConfig()
    WEB_UI = WebUIConfig()
    REMINDER = ReminderConfig()
    REPORT = ReportConfig()


CONFIG = Config()
