from aiogram import Router

from bot.handlers import start, words


def setup_routers() -> Router:
    """Собирает все роутеры в один. Порядок важен: общие обработчики идут последними."""
    root = Router()
    root.include_router(start.router)
    root.include_router(words.router)
    return root
