"""Интервальное повторение по алгоритму SM-2 (упрощённая версия, как в Anki).

Оценки:
  AGAIN — не вспомнил: карточка вернётся через 10 минут, прогресс сбрасывается;
  HARD  — вспомнил с трудом: интервал растёт медленно;
  GOOD  — вспомнил: интервал умножается на «лёгкость» карточки;
  EASY  — слишком легко: интервал растёт быстрее.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum

MIN_EASE = 1.3
RELEARN_DELAY = timedelta(minutes=10)


class Grade(IntEnum):
    AGAIN = 0
    HARD = 1
    GOOD = 2
    EASY = 3


@dataclass
class CardState:
    ease: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0


def review(state: CardState, grade: Grade, now: datetime) -> tuple[CardState, datetime]:
    """Возвращает новое состояние карточки и момент следующего показа."""
    ease, interval, reps, lapses = state.ease, state.interval_days, state.repetitions, state.lapses

    if grade == Grade.AGAIN:
        new = CardState(max(MIN_EASE, ease - 0.2), 0, 0, lapses + 1)
        return new, now + RELEARN_DELAY

    if grade == Grade.HARD:
        interval = 1 if reps == 0 else max(interval + 1, round(interval * 1.2))
        ease = max(MIN_EASE, ease - 0.15)
    elif grade == Grade.GOOD:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 3
        else:
            interval = max(interval + 1, round(interval * ease))
    else:  # EASY
        interval = 3 if reps == 0 else max(interval + 2, round(interval * ease * 1.3))
        ease = ease + 0.15

    new = CardState(ease, interval, reps + 1, lapses)
    return new, now + timedelta(days=interval)


def is_learned(interval_days: int) -> bool:
    """Слово считается выученным, когда интервал повторения дорос до 3 недель."""
    return interval_days >= 21
