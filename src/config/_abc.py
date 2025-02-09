from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_DIR_PATH = Path(__file__).resolve().parent.parent.parent


class ABCBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
