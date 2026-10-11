"""Тестовый стенд: настоящий Dispatcher + SQLite в памяти + фейковый Telegram.

Фейковая сессия бота не ходит в сеть, а складывает все запросы в список `sent`,
поэтому можно «нажимать кнопки» и проверять, что бот ответил.
"""
import os
from datetime import datetime, timezone
from typing import Any

os.environ.setdefault("BOT_TOKEN", "123456:TEST")

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User as TgUser

from bot.db.base import Base, make_engine, make_sessionmaker
from bot.handlers import setup_routers
from bot.middlewares.db import DbSessionMiddleware
from bot.services.seed import seed_words

USER_ID = 42
CHAT = Chat(id=USER_ID, type="private")
TG_USER = TgUser(id=USER_ID, is_bot=False, first_name="Vlad")


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[TelegramMethod] = []
        self._message_id = 1000

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:
        self.sent.append(method)
        name = type(method).__name__
        if name in ("SendMessage", "SendVoice", "SendAudio", "EditMessageText"):
            self._message_id += 1
            return Message(message_id=self._message_id, date=datetime.now(timezone.utc), chat=CHAT,
                           text=getattr(method, "text", None) or getattr(method, "caption", None))
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    async def close(self) -> None:
        pass


class Harness:
    def __init__(self, dp: Dispatcher, bot: Bot, session: FakeSession, sessionmaker) -> None:
        self.dp, self.bot, self.fake, self.sessionmaker = dp, bot, session, sessionmaker
        self._update_id = 0

    def _next_id(self) -> int:
        self._update_id += 1
        return self._update_id

    async def text(self, text: str, **extra) -> list[TelegramMethod]:
        start = len(self.fake.sent)
        msg = Message(message_id=self._next_id(), date=datetime.now(timezone.utc), chat=CHAT,
                      from_user=TG_USER, text=text, **extra)
        await self.dp.feed_update(self.bot, Update(update_id=self._next_id(), message=msg))
        return self._check(self.fake.sent[start:])

    async def click(self, data: str) -> list[TelegramMethod]:
        start = len(self.fake.sent)
        msg = Message(message_id=self._next_id(), date=datetime.now(timezone.utc), chat=CHAT, text="…")
        cb = CallbackQuery(id=str(self._next_id()), from_user=TG_USER, chat_instance="x", data=data, message=msg)
        await self.dp.feed_update(self.bot, Update(update_id=self._next_id(), callback_query=cb))
        return self._check(self.fake.sent[start:])

    def _check(self, methods: list[TelegramMethod]) -> list[TelegramMethod]:
        """Падаем, если бот поймал исключение (обработчик ошибок пишет «Что-то сломалось»)."""
        for text in self.texts(methods):
            assert "Что-то сломалось" not in text, "хендлер упал с исключением, см. лог"
        return methods

    def texts(self, methods: list[TelegramMethod]) -> list[str]:
        return [m.text for m in methods if getattr(m, "text", None)]

    def buttons(self, methods: list[TelegramMethod]) -> list[tuple[str, str]]:
        """Все inline-кнопки из ответов: (текст, callback_data)."""
        result = []
        for m in methods:
            markup = getattr(m, "reply_markup", None)
            for row in getattr(markup, "inline_keyboard", None) or []:
                for b in row:
                    result.append((b.text, b.callback_data))
        return result


@pytest.fixture
async def harness(monkeypatch):
    # Озвучка в тестах не ходит в интернет
    async def fake_speech(*args, **kwargs):
        return True
    for module in ("bot.handlers.words", "bot.handlers.listening"):
        monkeypatch.setattr(f"{module}.send_speech", fake_speech)

    # По умолчанию SQLite в памяти; для проверки на PostgreSQL задай TEST_DATABASE_URL
    engine = make_engine(os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = make_sessionmaker(engine)
    await seed_words(sessionmaker)

    fake = FakeSession()
    bot = Bot("123456:TEST", session=fake)
    dp = Dispatcher()
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    # Роутеры — глобальные объекты модулей; между тестами отвязываем их от старого диспетчера
    from bot import handlers
    for module in (handlers.start, handlers.words, handlers.grammar, handlers.listening, handlers.quests,
                   handlers.sprint, handlers.profile, handlers.check, handlers.fallback):
        module.router._parent_router = None
    dp.include_router(setup_routers())
    yield Harness(dp, bot, fake, sessionmaker)
    await engine.dispose()
