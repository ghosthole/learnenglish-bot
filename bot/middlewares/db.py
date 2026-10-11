"""Мидлварь: открывает сессию БД на каждый апдейт и подгружает (или создаёт) пользователя.

В хендлерах достаточно объявить аргументы `session: AsyncSession` и `user: User`.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import get_settings
from bot.db.models import User


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self.sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.sessionmaker() as session:
            data["session"] = session
            tg_user = data.get("event_from_user")
            if tg_user is not None:
                user = await session.get(User, tg_user.id)
                if user is None:
                    user = User(
                        id=tg_user.id,
                        username=tg_user.username,
                        first_name=tg_user.first_name,
                        timezone=get_settings().default_timezone,
                    )
                    session.add(user)
                    await session.flush()
                data["user"] = user
            result = await handler(event, data)
            await session.commit()
            return result
