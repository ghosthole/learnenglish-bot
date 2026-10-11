"""Если нажата кнопка меню или введена команда — выходим из текущего задания.

Иначе, например, нажатие «📚 Слова» во время урока засчиталось бы как ответ.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.menu import ALL_BUTTONS


class MenuResetMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        text = event.text or ""
        state: FSMContext | None = data.get("state")
        if state is not None and (text in ALL_BUTTONS or text.startswith("/")):
            await state.set_state(None)
            # raw_state уже вычислен до мидлвари, обновляем его для фильтров состояний
            data["raw_state"] = None
        return await handler(event, data)
