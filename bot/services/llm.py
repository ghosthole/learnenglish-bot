"""Опциональная интеграция с Claude API.

Включается, если в .env задан ANTHROPIC_API_KEY. Без ключа функции возвращают None,
и бот работает на готовых ответах. Используется в двух местах:
  - judge_answer: засчитать ли перевод, который не совпал с готовыми вариантами;
  - review_writing: разбор мини-сочинений из квестов.
"""
import html
import logging

import anthropic
from pydantic import BaseModel

from bot.config import get_settings
from bot.services.checker import CheckResult

log = logging.getLogger(__name__)

SYSTEM = (
    "You are a friendly English tutor for Vlad, a Russian-speaking learner moving from A2 to B1. "
    "His known weak spots: verb forms and tenses (3rd person -s, past simple, irregular verbs, -ing after "
    "start/like), conditionals (if + past, would), articles, plurals and prepositions. "
    "Always write explanations in Russian, short and casual, like a supportive older friend. "
    "Be precise about grammar: do not accept a sentence with a real grammar mistake, but accept any "
    "correct and natural alternative wording, and ignore capitalisation and punctuation."
)

_client: anthropic.AsyncAnthropic | None = None


def enabled() -> bool:
    return get_settings().ai_enabled


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


class Verdict(BaseModel):
    correct: bool
    comment_ru: str


class Mistake(BaseModel):
    wrong: str
    right: str
    why_ru: str


class WritingReview(BaseModel):
    corrected_text: str
    mistakes: list[Mistake]
    praise_ru: str


async def _parse(prompt: str, output_format: type[BaseModel]) -> BaseModel | None:
    settings = get_settings()
    try:
        response = await client().beta.messages.parse(
            model=settings.anthropic_model,
            max_tokens=8000,
            system=SYSTEM,
            output_config={"effort": settings.anthropic_effort},
            # Если модель откажется отвечать, запрос автоматически повторится на запасной модели
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
            output_format=output_format,
        )
    except anthropic.APIConnectionError:
        log.warning("Claude API недоступен")
        return None
    except anthropic.APIStatusError as e:
        log.warning("Ошибка Claude API %s: %s", e.status_code, e.message)
        return None
    if response.stop_reason == "refusal":
        return None
    return response.parsed_output


async def judge_answer(task: str, answer: str, reference: str) -> CheckResult | None:
    prompt = (
        f"Exercise: {task}\n"
        f"Reference answer: {reference}\n"
        f"Student's answer: {answer}\n\n"
        "Is the student's answer correct for this exercise? If it is wrong, name the exact mistake "
        "in comment_ru (1-2 sentences). If it is right, comment_ru is a short confirmation, and you may "
        "mention a more natural option."
    )
    verdict = await _parse(prompt, Verdict)
    if verdict is None:
        return None
    return CheckResult(ok=verdict.correct, comment=verdict.comment_ru)


async def review_writing(task: str, text: str) -> str | None:
    """Возвращает готовый HTML-разбор текста или None."""
    prompt = (
        f"Task (in Russian): {task}\n\nStudent's text:\n{text}\n\n"
        "Correct the text. List up to 5 most important mistakes (wrong fragment, right fragment, why in "
        "Russian). If there are no mistakes, return an empty list. praise_ru: one short sentence about what "
        "was good."
    )
    review = await _parse(prompt, WritingReview)
    if review is None:
        return None
    lines = [f"👍 {html.escape(review.praise_ru)}"]
    for m in review.mistakes:
        lines.append(f"❌ <s>{html.escape(m.wrong)}</s> → ✅ <b>{html.escape(m.right)}</b>\n   "
                     f"<i>{html.escape(m.why_ru)}</i>")
    if review.mistakes:
        lines.append(f"\n📝 <b>Исправленный вариант:</b>\n{html.escape(review.corrected_text)}")
    else:
        lines.append("Ошибок нет, чисто 🔥")
    return "\n".join(lines)
