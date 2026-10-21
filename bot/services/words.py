"""Запросы к словам и карточкам повторения."""
import random
import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User, UserWord, Word
from bot.services import srs
from bot.services.timeutils import start_of_user_day_utc, utcnow

# Как часто давать новые слова из каждой темы: вес 2 — основные темы (быт, работа,
# путешествия), 1 — дополнительные. Бот выравнивает темы по весам с учётом уже
# изученных слов, поэтому если ты много учил путешествия, дальше пойдут быт и работа.
TOPIC_WEIGHTS = {
    "daily": 2, "home": 2, "work": 2, "travel": 2, "shopping": 2, "city": 2, "health": 2, "food": 2,
    "study": 1, "irregular": 1, "connectors": 1, "phrasal": 1, "feelings": 1, "series": 1, "slang": 1,
}

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


def base_form(en: str) -> str:
    """«to miss (a flight)» → «miss»: чтобы не давать слово, которое уже есть (например, из Anki)."""
    en = re.sub(r"\(.*?\)", "", en.lower()).strip()
    return en.removeprefix("to ").strip()


async def pick_new_words(session: AsyncSession, user: User, limit: int) -> list[Word]:
    """Слова из общего словаря, которых ещё нет у пользователя, вперемешку по темам."""
    if limit <= 0:
        return []
    known = select(UserWord.word_id).where(UserWord.user_id == user.id)
    candidates = list(await session.scalars(
        select(Word).where(Word.owner_id.is_(None), Word.id.not_in(known))
    ))
    my_words = list(await session.scalars(
        select(Word).join(UserWord, UserWord.word_id == Word.id).where(UserWord.user_id == user.id)))
    my_forms = {base_form(w.en) for w in my_words}
    candidates = [w for w in candidates if base_form(w.en) not in my_forms]

    # Сколько слов каждой темы уже в изучении — от этого зависит, какую тему дать следующей
    have: dict[str, int] = {}
    for w in my_words:
        have[w.topic] = have.get(w.topic, 0) + 1
    by_topic: dict[str, list[Word]] = {}
    random.shuffle(candidates)
    for w in sorted(candidates, key=lambda w: w.level != "A2"):  # внутри темы сначала A2
        by_topic.setdefault(w.topic, []).append(w)

    picked: list[Word] = []
    while len(picked) < limit and by_topic:
        topic = min(by_topic, key=lambda t: ((have.get(t, 0) + 1) / TOPIC_WEIGHTS.get(t, 1), random.random()))
        picked.append(by_topic[topic].pop(0))
        have[topic] = have.get(topic, 0) + 1
        if not by_topic[topic]:
            del by_topic[topic]
    return picked


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
