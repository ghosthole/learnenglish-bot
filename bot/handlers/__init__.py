from aiogram import Router

from bot.handlers import check, fallback, grammar, listening, profile, quests, sprint, start, words
from bot.middlewares.menu import MenuResetMiddleware


def setup_routers() -> Router:
    """Собирает все роутеры в один. Порядок важен: общие обработчики идут последними."""
    root = Router()
    root.message.outer_middleware(MenuResetMiddleware())
    root.include_router(start.router)
    root.include_router(words.router)
    root.include_router(grammar.router)
    root.include_router(listening.router)
    root.include_router(quests.router)
    root.include_router(sprint.router)
    root.include_router(profile.router)
    root.include_router(check.router)
    root.include_router(fallback.router)  # всегда последним
    return root
