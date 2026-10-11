"""Точка входа: python -m bot"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_settings
from bot.db.base import make_engine, make_sessionmaker
from bot.handlers import setup_routers
from bot.middlewares.db import DbSessionMiddleware
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

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
