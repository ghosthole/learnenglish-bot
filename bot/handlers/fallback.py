"""Последний роутер: непонятные сообщения и ошибки."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, ErrorEvent, Message

from bot.keyboards.menu import main_menu

router = Router()
log = logging.getLogger(__name__)


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    await message.answer("Не понял 🤔 Выбери что-нибудь в меню или жми /help", reply_markup=main_menu())


@router.callback_query()
async def stale_button(callback: CallbackQuery) -> None:
    await callback.answer("Кнопка устарела, открой раздел заново")


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    log.exception("Ошибка при обработке апдейта", exc_info=event.exception)
    update = event.update
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message is not None:
        try:
            await message.answer("😵 Что-то сломалось. Уже записал в лог. Попробуй ещё раз или /start")
        except Exception:
            pass
    return True
