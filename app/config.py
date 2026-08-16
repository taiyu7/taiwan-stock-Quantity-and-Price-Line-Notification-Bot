from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    line_channel_access_token: str = ""
    line_channel_secret: str = ""
    database_url: str = "sqlite:///./data/app.db"
    app_base_url: str = "http://localhost:8000"
    check_interval_seconds: int = 30
    alert_cooldown_seconds: int = 300
    timezone: str = "Asia/Taipei"
    enable_scheduler: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
