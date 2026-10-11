"""Проверка письменных ответов.

Сначала ответ сравнивается с готовыми правильными вариантами (после нормализации).
Если не совпало и подключён Claude API, ответ дополнительно проверяет нейросеть —
она может засчитать другой верный вариант и объяснить ошибку.
"""
import re
from dataclasses import dataclass

_CONTRACTIONS = [
    (r"\bwon't\b", "will not"),
    (r"\bcan't\b", "can not"),
    (r"\bcannot\b", "can not"),
    (r"\bshan't\b", "shall not"),
    (r"n't\b", " not"),
    (r"'m\b", " am"),
    (r"'re\b", " are"),
    (r"'ve\b", " have"),
    (r"'ll\b", " will"),
    (r"\b(it|he|she|that|what|there|where|who)'s\b", r"\1 is"),
]


def normalize(text: str) -> str:
    """Приводит ответ к единому виду: регистр, апострофы, пунктуация, сокращения."""
    text = text.lower().strip()
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    for pattern, repl in _CONTRACTIONS:
        text = re.sub(pattern, repl, text)
    text = re.sub(r"[^\w\s'-]", " ", text)  # убираем знаки препинания
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class CheckResult:
    ok: bool
    comment: str = ""  # пояснение от нейросети, если она проверяла


def check_static(answer: str, accepted: list[str]) -> bool:
    norm = normalize(answer)
    return any(norm == normalize(a) for a in accepted)


async def check_answer(answer: str, accepted: list[str], task: str) -> CheckResult:
    if check_static(answer, accepted):
        return CheckResult(ok=True)
    from bot.services import llm  # локальный импорт: модуль нужен только при включённом ИИ

    if llm.enabled():
        verdict = await llm.judge_answer(task=task, answer=answer, reference=accepted[0])
        if verdict is not None:
            return verdict
    return CheckResult(ok=False)
