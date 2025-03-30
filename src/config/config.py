from pydantic_settings import SettingsConfigDict

from ._abc import ABCBaseSettings


class TGBotConfig(ABCBaseSettings):
    BOT_TOKEN: str

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


class Config:
    TELEGRAM = TGBotConfig()
    OPENAI = OpenAIConfig()
    PROXY = ProxyConfig()
    SMTP = SMTPConfig()


CONFIG = Config()
