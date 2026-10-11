"""Настройки бота. Читаются из переменных окружения или файла .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    database_url: str = "postgresql+asyncpg://bot:bot@localhost:5432/learnenglish"
    default_timezone: str = "Europe/Moscow"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "low"  # low | medium | high — глубина размышлений модели

    tts_voice: str = "en-US-AriaNeural"
    audio_cache_dir: str = "audio_cache"
    tts_proxy: str = ""  # например http://user:pass@host:port, если сервис озвучки недоступен напрямую

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
