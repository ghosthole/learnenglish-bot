"""Точка входа: python -m bot"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import get_settings
from bot.db.base import make_engine, make_sessionmaker
from bot.handlers import setup_routers
from bot.middlewares.db import DbSessionMiddleware
from bot.services.reminders import setup_scheduler
from bot.services.seed import seed_words


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()

    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    await seed_words(sessionmaker)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    dp.include_router(setup_routers())

    scheduler = setup_scheduler(bot, sessionmaker)
    scheduler.start()

    await bot.set_my_commands([
        BotCommand(command="sprint", description="⚡ 5-минутка"),
        BotCommand(command="review", description="🔁 Повторить слова"),
        BotCommand(command="grammar", description="📖 Грамматика"),
        BotCommand(command="listen", description="🎧 Аудирование"),
        BotCommand(command="quests", description="🎯 Квесты"),
        BotCommand(command="check", description="🧪 Проверка"),
        BotCommand(command="add", description="➕ Добавить слова"),
        BotCommand(command="anki", description="🗂 Импорт из Anki"),
        BotCommand(command="profile", description="👤 Профиль"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="help", description="Все команды"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
