"""Главное меню (кнопки под полем ввода)."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_SPRINT = "⚡ 5-минутка"
BTN_WORDS = "📚 Слова"
BTN_GRAMMAR = "📖 Грамматика"
BTN_LISTENING = "🎧 Аудирование"
BTN_QUESTS = "🎯 Квесты"
BTN_CHECK = "🧪 Проверка"
BTN_PROFILE = "👤 Профиль"
BTN_SETTINGS = "⚙️ Настройки"

ALL_BUTTONS = {BTN_SPRINT, BTN_WORDS, BTN_GRAMMAR, BTN_LISTENING, BTN_QUESTS, BTN_CHECK, BTN_PROFILE, BTN_SETTINGS}


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [BTN_SPRINT],
        [BTN_WORDS, BTN_GRAMMAR],
        [BTN_LISTENING, BTN_QUESTS],
        [BTN_CHECK, BTN_PROFILE],
        [BTN_SETTINGS],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )
