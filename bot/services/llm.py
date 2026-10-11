"""Опциональная интеграция с Claude API. Без ANTHROPIC_API_KEY все функции молча отключены."""
import logging

from bot.config import get_settings
from bot.services.checker import CheckResult

log = logging.getLogger(__name__)


def enabled() -> bool:
    return get_settings().ai_enabled


async def judge_answer(task: str, answer: str, reference: str) -> CheckResult | None:
    return None  # реализация появится в следующем коммите


async def review_writing(task: str, text: str) -> str | None:
    return None  # реализация появится в следующем коммите
