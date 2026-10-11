"""Заливка встроенного словаря в базу при запуске бота."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.content.words import ALL_WORDS
from bot.db.models import Word

log = logging.getLogger(__name__)


async def seed_words(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        existing = set(await session.scalars(select(Word.en).where(Word.owner_id.is_(None))))
        added = 0
        for en, ru, example, topic, level in ALL_WORDS:
            if en in existing:
                continue
            session.add(Word(en=en, ru=ru, example=example, topic=topic, level=level))
            existing.add(en)
            added += 1
        await session.commit()
    if added:
        log.info("Добавлено %d новых слов в словарь", added)
