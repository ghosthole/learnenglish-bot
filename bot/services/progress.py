"""Оценка пути к B1 — грубая, но наглядная метрика мотивации.

40% — пройденные уроки грамматики, 35% — словарь, 25% — результаты проверок.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.content.grammar import LESSONS
from bot.db.models import GrammarProgress, TestResult, User, UserWord

VOCAB_TARGET = 500  # столько «рабочих» слов поверх базы A2 — хороший ориентир для B1


async def b1_progress(session: AsyncSession, user: User) -> int:
    passed = await session.scalar(
        select(func.count()).select_from(GrammarProgress)
        .where(GrammarProgress.user_id == user.id, GrammarProgress.best_score >= 70)) or 0
    grammar = passed / len(LESSONS)

    learned = await session.scalar(
        select(func.count()).select_from(UserWord)
        .where(UserWord.user_id == user.id, UserWord.interval_days >= 21)) or 0
    learning = await session.scalar(
        select(func.count()).select_from(UserWord)
        .where(UserWord.user_id == user.id, UserWord.interval_days < 21, UserWord.repetitions >= 2)) or 0
    vocab = min(1.0, (learned + 0.5 * learning) / VOCAB_TARGET)

    recent = list(await session.scalars(
        select(TestResult).where(TestResult.user_id == user.id, TestResult.kind == "weekly")
        .order_by(TestResult.created_at.desc()).limit(3)))
    checks = sum(r.score / r.total for r in recent if r.total) / len(recent) if recent else 0

    return round(100 * (0.4 * grammar + 0.35 * vocab + 0.25 * checks))
