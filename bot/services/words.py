"""Запросы к словам и карточкам повторения."""
import random
import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User, UserWord, Word
from bot.services import srs
from bot.services.timeutils import start_of_user_day_utc, utcnow

# Порядок, в котором выдаются новые слова: сначала самое нужное под цели
TOPIC_PRIORITY = ["travel", "daily", "series", "irregular", "food", "feelings",
                  "connectors", "study", "phrasal", "slang"]


async def count_due(session: AsyncSession, user: User, now: datetime | None = None) -> int:
    now = now or utcnow()
    return await session.scalar(
        select(func.count()).select_from(UserWord)
        .where(UserWord.user_id == user.id, UserWord.due_at <= now)
    ) or 0


async def get_due_cards(session: AsyncSession, user: User, limit: int = 20) -> list[UserWord]:
    result = await session.scalars(
        select(UserWord)
        .where(UserWord.user_id == user.id, UserWord.due_at <= utcnow())
        .order_by(UserWord.due_at)
        .limit(limit)
    )
    return list(result)


async def count_new_today(session: AsyncSession, user: User) -> int:
    """Сколько встроенных слов пользователь начал учить сегодня (свои слова не считаются)."""
    return await session.scalar(
        select(func.count()).select_from(UserWord).join(Word)
        .where(
            UserWord.user_id == user.id,
            Word.owner_id.is_(None),
            UserWord.created_at >= start_of_user_day_utc(user),
        )
    ) or 0


async def pick_new_words(session: AsyncSession, user: User, limit: int) -> list[Word]:
    """Слова из общего словаря, которых ещё нет у пользователя."""
    if limit <= 0:
        return []
    known = select(UserWord.word_id).where(UserWord.user_id == user.id)
    candidates = list(await session.scalars(
        select(Word).where(Word.owner_id.is_(None), Word.id.not_in(known))
    ))

    def priority(w: Word) -> tuple[int, int]:
        level = 0 if w.level == "A2" else 1
        topic = TOPIC_PRIORITY.index(w.topic) if w.topic in TOPIC_PRIORITY else 99
        return level, topic

    candidates.sort(key=priority)
    # Берём из начала списка, но слегка перемешиваем, чтобы темы чередовались
    pool = candidates[: limit * 3]
    random.shuffle(pool)
    return pool[:limit]


async def start_learning(session: AsyncSession, user: User, words: list[Word]) -> list[UserWord]:
    cards = [UserWord(user_id=user.id, word_id=w.id, due_at=utcnow()) for w in words]
    session.add_all(cards)
    await session.flush()
    return cards


async def add_custom_word(
    session: AsyncSession, user: User, en: str, ru: str, example: str | None = None, topic: str = "custom"
) -> tuple[UserWord, bool]:
    """Добавляет слово пользователя в повторение. Возвращает (карточка, создано_ли_новое)."""
    en = en.strip()
    word = await session.scalar(
        select(Word).where(func.lower(Word.en) == en.lower(),
                           (Word.owner_id == user.id) | Word.owner_id.is_(None))
    )
    if word is None:
        word = Word(en=en, ru=ru.strip(), example=example, topic=topic, level="B1", owner_id=user.id)
        session.add(word)
        await session.flush()

    card = await session.scalar(
        select(UserWord).where(UserWord.user_id == user.id, UserWord.word_id == word.id)
    )
    if card is not None:
        return card, False
    card = UserWord(user_id=user.id, word_id=word.id, due_at=utcnow())
    session.add(card)
    await session.flush()
    return card, True


async def apply_grade(session: AsyncSession, card: UserWord, grade: srs.Grade) -> None:
    state = srs.CardState(card.ease, card.interval_days, card.repetitions, card.lapses)
    now = utcnow()
    new, due = srs.review(state, grade, now)
    card.ease, card.interval_days = new.ease, new.interval_days
    card.repetitions, card.lapses = new.repetitions, new.lapses
    card.due_at = due
    card.last_reviewed_at = now
    await session.flush()


async def quiz_options(session: AsyncSession, word: Word, n: int = 4, field: str = "ru") -> list[str]:
    """Правильный ответ + неправильные варианты (по возможности из той же темы)."""
    correct = getattr(word, field)
    column = getattr(Word, field)
    same_topic = list(await session.scalars(
        select(column).where(Word.id != word.id, Word.topic == word.topic, Word.owner_id.is_(None))
    ))
    other = list(await session.scalars(
        select(column).where(Word.id != word.id, Word.owner_id.is_(None)).limit(200)
    ))
    pool = [x for x in dict.fromkeys(same_topic + other) if x != correct]
    random.shuffle(pool)
    options = pool[: n - 1] + [correct]
    random.shuffle(options)
    return options


async def word_stats(session: AsyncSession, user: User) -> dict[str, int]:
    total = await session.scalar(
        select(func.count()).select_from(UserWord).where(UserWord.user_id == user.id)) or 0
    learned = await session.scalar(
        select(func.count()).select_from(UserWord)
        .where(UserWord.user_id == user.id, UserWord.interval_days >= 21)) or 0
    return {"total": total, "learned": learned, "learning": total - learned}


_NUMBERING_RE = re.compile(r"^\s*(?:\d+[.)]|[-•*])\s*")
# Сначала ищем разделитель с пробелами вокруг, чтобы не резать слова вроде «binge-watch»
_SEPARATOR_RE = re.compile(r"\s+[—–-]\s+|\s*[—–:=]\s*")


def parse_word_lines(text: str) -> list[tuple[str, str]]:
    """Разбирает строки вида «word - перевод» (также «—», «:», «=»; можно с нумерацией)."""
    pairs = []
    for line in text.splitlines():
        line = _NUMBERING_RE.sub("", line).strip()
        if not line:
            continue
        parts = _SEPARATOR_RE.split(line, maxsplit=1)
        if len(parts) < 2:
            parts = line.split("-", 1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            pairs.append((parts[0].strip(), parts[1].strip()))
    return pairs
