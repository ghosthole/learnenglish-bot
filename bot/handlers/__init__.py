from aiogram import Router

from bot.handlers import grammar, start, words
from bot.middlewares.menu import MenuResetMiddleware


def setup_routers() -> Router:
    """Собирает все роутеры в один. Порядок важен: общие обработчики идут последними."""
    root = Router()
    root.message.outer_middleware(MenuResetMiddleware())
    root.include_router(start.router)
    root.include_router(words.router)
    root.include_router(grammar.router)
    return root
