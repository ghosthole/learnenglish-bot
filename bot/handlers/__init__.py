from aiogram import Router

from bot.handlers import start


def setup_routers() -> Router:
    """Собирает все роутеры в один. Порядок важен: общие обработчики идут последними."""
    root = Router()
    root.include_router(start.router)
    return root
