"""Разнообразие заданий: что пользователь уже видел и что дать следующим.

Каждый показанный вопрос (грамматика, перевод) записывается в seen_items.
При выборе следующего задания сначала берём те, что ещё не попадались,
потом — те, что попадались давно. Так одно и то же предложение не
повторяется каждый день.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import SeenItem, User
from bot.services.timeutils import utcnow

_NEVER = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _aware(dt: datetime) -> datetime:
    # SQLite возвращает время без часового пояса — считаем, что это UTC
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def last_seen(session: AsyncSession, user: User, keys: list[str]) -> dict[str, datetime]:
    if not keys:
        return {}
    rows = await session.execute(
        select(SeenItem.item_key, SeenItem.last_seen_at)
        .where(SeenItem.user_id == user.id, SeenItem.item_key.in_(keys)))
    return {k: _aware(t) for k, t in rows}


async def mark_seen(session: AsyncSession, user: User, key: str) -> None:
    item = await session.scalar(
        select(SeenItem).where(SeenItem.user_id == user.id, SeenItem.item_key == key))
    if item is None:
        session.add(SeenItem(user_id=user.id, item_key=key))
    else:
        item.times_seen += 1
        item.last_seen_at = utcnow()
    await session.flush()


async def pick_fresh(session: AsyncSession, user: User, candidates: list[str], n: int = 1,
                     exclude: set[str] | None = None) -> list[str]:
    """n ключей из candidates: сначала невиданные, затем самые давние. Внутри — случайно."""
    pool = [k for k in dict.fromkeys(candidates) if k not in (exclude or set())]
    if not pool:
        return []
    seen = await last_seen(session, user, pool)
    random.shuffle(pool)
    pool.sort(key=lambda k: seen.get(k, _NEVER))
    # Берём не строго самые старые, а случайно из «давних», чтобы порядок не был предсказуем
    head = pool[: max(n * 3, n)]
    random.shuffle(head)
    return head[:n]


async def seen_recently(session: AsyncSession, user: User, keys: list[str],
                        hours: float) -> set[str]:
    border = utcnow() - timedelta(hours=hours)
    return {k for k, t in (await last_seen(session, user, keys)).items() if t > border}
