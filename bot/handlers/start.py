from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.db.models import User
from bot.keyboards.menu import main_menu

router = Router()

WELCOME = """Yo, {name}! 👋 Я твой English-коуч.

<b>Где ты сейчас:</b> A2 🟨
<b>Куда идём:</b> B1 🟩

По тесту видно, что понимаешь ты уже неплохо, а подтянуть надо три вещи:
1️⃣ формы глагола и времена (goes, went, started watching)
2️⃣ условные предложения с if (If I had…)
3️⃣ артикли, предлоги и множественное число (a town, two people, travel to)

<b>Как это будет работать:</b>
📚 слова с интервальным повторением — учишь 7 новых в день, бот сам напомнит, когда повторить
📖 грамматика короткими уроками ровно под твои слабые места
🎧 аудирование: озвученные истории + видео под твой уровень
🎯 квесты за очки: например, посмотреть серию с англ. субтитрами и выписать 10 слов
🧪 проверки каждую неделю, чтобы видеть рост
🔥 XP, уровни, стрики, ачивки и лутбоксы

Не знаешь, с чего начать? Жми <b>⚡ 5-минутка</b>: короткий микс всего понемногу."""

HELP = """<b>Команды</b>
/start — начало и меню
/sprint — 5-минутка (микс заданий)
/review — повторить слова
/new — новые слова
/add — добавить свои слова
/grammar — уроки грамматики
/listen — аудирование
/quests — квесты
/check — проверка знаний
/profile — профиль и статистика
/settings — напоминания и цели
/cancel — выйти из текущего задания"""


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    name = user.first_name or "друг"
    await message.answer(WELCOME.format(name=name), reply_markup=main_menu())
    await message.answer(
        "Поехали? 🚀",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Первая 5-минутка", callback_data="sprint:start")],
        ]),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("cancel"))
@router.message(F.text.lower().in_({"отмена", "стоп", "cancel"}))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ок, вышли. Возвращайся в меню 👇", reply_markup=main_menu())
