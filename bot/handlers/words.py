"""Слова: новые слова, повторение (SRS), квиз и добавление своих слов."""
import html
import random

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User, UserWord
from bot.keyboards.menu import BTN_WORDS
from bot.services import gamification as game
from bot.services import words as words_service
from bot.services.srs import Grade
from bot.services.tts import send_speech

router = Router()

SESSION_LIMIT = 15  # карточек за один заход: коротко, чтобы не надоедало


class WordCb(CallbackData, prefix="w"):
    action: str  # show | grade | pick | say
    card_id: int = 0
    value: int = 0


class AddWords(StatesGroup):
    waiting = State()


def esc(text: str | None) -> str:
    return html.escape(text or "")


# ---------- Меню слов ----------

@router.message(F.text == BTN_WORDS)
@router.message(Command("words"))
async def words_menu(message: Message, session: AsyncSession, user: User) -> None:
    due = await words_service.count_due(session, user)
    new_left = max(0, user.new_words_per_day - await words_service.count_new_today(session, user))
    stats = await words_service.word_stats(session, user)
    text = (
        "📚 <b>Слова</b>\n\n"
        f"🔁 На повторение: <b>{due}</b>\n"
        f"✨ Новых на сегодня осталось: <b>{new_left}</b>\n"
        f"🧠 Выучено: <b>{stats['learned']}</b> · в процессе: <b>{stats['learning']}</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🔁 Повторить ({due})", callback_data="words:review")
    kb.button(text="✨ Новые слова", callback_data="words:new")
    kb.button(text="➕ Добавить свои", callback_data="words:add")
    kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup())


# ---------- Новые слова ----------

async def show_new_words(message: Message, session: AsyncSession, user: User, extra: bool = False) -> None:
    left = user.new_words_per_day - await words_service.count_new_today(session, user)
    limit = 5 if extra else left
    if limit <= 0:
        kb = InlineKeyboardBuilder()
        kb.button(text="😤 Хочу ещё 5", callback_data="words:more")
        kb.button(text="🔁 Повторить", callback_data="words:review")
        await message.answer("На сегодня норма новых слов выполнена ✅\nМозгу нужно время, чтобы их уложить.",
                             reply_markup=kb.as_markup())
        return

    new_words = await words_service.pick_new_words(session, user, limit)
    if not new_words:
        await message.answer("Встроенный словарь закончился 🤯 Добавляй свои слова через ➕")
        return
    await words_service.start_learning(session, user, new_words)

    lines = ["✨ <b>Новые слова</b>\n"]
    for w in new_words:
        lines.append(f"• <b>{esc(w.en)}</b> — {esc(w.ru)}\n   <i>{esc(w.example)}</i>")
    lines.append("\nПрочитай вслух каждый пример 🗣 Сейчас сразу закрепим.")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Закрепить", callback_data="words:review")
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


@router.message(Command("new"))
async def cmd_new(message: Message, session: AsyncSession, user: User) -> None:
    await show_new_words(message, session, user)


@router.callback_query(F.data == "words:new")
async def cb_new(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    await callback.answer()
    await show_new_words(callback.message, session, user)


@router.callback_query(F.data == "words:more")
async def cb_more(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    await callback.answer()
    await show_new_words(callback.message, session, user, extra=True)


# ---------- Повторение ----------

async def send_card(message: Message, session: AsyncSession, state: FSMContext, card: UserWord) -> None:
    """Показывает карточку в случайном формате: «вспомни перевод» или квиз из 4 вариантов."""
    word = card.word
    mode = "flip" if card.repetitions == 0 else random.choice(["flip", "quiz_ru", "quiz_en"])

    if mode == "flip":
        kb = InlineKeyboardBuilder()
        kb.button(text="👀 Показать", callback_data=WordCb(action="show", card_id=card.id))
        kb.button(text="🔊", callback_data=WordCb(action="say", card_id=card.id))
        await message.answer(f"🤔 Что значит\n\n<b>{esc(word.en)}</b>", reply_markup=kb.as_markup())
        return

    field = "ru" if mode == "quiz_ru" else "en"
    options = await words_service.quiz_options(session, word, field=field)
    correct = options.index(getattr(word, field))
    await state.update_data(quiz={"card_id": card.id, "correct": correct})
    question = (f"🎯 Выбери перевод:\n\n<b>{esc(word.en)}</b>" if field == "ru"
                else f"🎯 Как сказать по-английски:\n\n<b>{esc(word.ru)}</b>")
    kb = InlineKeyboardBuilder()
    for i, opt in enumerate(options):
        kb.button(text=opt[:60], callback_data=WordCb(action="pick", card_id=card.id, value=i))
    kb.adjust(1)
    await message.answer(question, reply_markup=kb.as_markup())


async def next_card(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    """Следующий шаг после ответа: продолжение 5-минутки или следующая карточка."""
    data = await state.get_data()
    if data.get("sprint"):
        from bot.handlers.sprint import sprint_next  # локальный импорт, чтобы не было циклов
        await sprint_next(message, session, user, state)
        return

    done = data.get("review_done", 0)
    cards = await words_service.get_due_cards(session, user, limit=1)
    if not cards or done >= SESSION_LIMIT:
        await finish_review(message, session, user, state)
        return
    await send_card(message, session, state, cards[0])


async def finish_review(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    data = await state.get_data()
    done, correct = data.get("review_done", 0), data.get("review_correct", 0)
    await state.update_data(review_done=0, review_correct=0, combo=0)
    left = await words_service.count_due(session, user)
    if done == 0:
        await message.answer("🎉 Повторять пока нечего! Возьми новые слова или загляни в квесты.")
        return
    text = f"🏁 <b>Сессия закончена</b>\nКарточек: {done} · верно: {correct}"
    if left:
        text += f"\nЕщё ждут повторения: {left}"
    loot = await game.maybe_lootbox(session, user)
    if loot:
        text += "\n\n" + loot
    kb = InlineKeyboardBuilder()
    if left:
        kb.button(text="🔁 Ещё круг", callback_data="words:review")
    kb.button(text="✨ Новые слова", callback_data="words:new")
    await message.answer(text, reply_markup=kb.as_markup())


async def register_answer(
    message: Message, session: AsyncSession, user: User, state: FSMContext,
    card: UserWord, grade: Grade, feedback: str,
) -> None:
    await words_service.apply_grade(session, card, grade)
    data = await state.get_data()
    ok = grade >= Grade.HARD
    combo = data.get("combo", 0) + 1 if ok else 0
    await state.update_data(
        combo=combo,
        review_done=data.get("review_done", 0) + 1,
        review_correct=data.get("review_correct", 0) + int(ok),
    )
    xp = {Grade.AGAIN: 0, Grade.HARD: 1, Grade.GOOD: 2, Grade.EASY: 2}[grade]
    if combo >= 5:
        xp += 1  # бонус за серию верных ответов
    parts = [feedback]
    if xp:
        parts.append((await game.award(session, user, xp, "word")).text())
    if combo_msg := game.combo_message(combo):
        parts.append(combo_msg)
    if combo == 10:
        if msg := await game.grant_achievement(session, user, "combo_10"):
            parts.append(msg)
    await message.answer("\n".join(parts))
    await next_card(message, session, user, state)


@router.message(Command("review"))
async def cmd_review(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    await state.update_data(sprint=None, review_done=0, review_correct=0, combo=0)
    await next_card(message, session, user, state)


@router.callback_query(F.data == "words:review")
async def cb_review(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(sprint=None, review_done=0, review_correct=0, combo=0)
    await next_card(callback.message, session, user, state)


async def get_card(session: AsyncSession, user: User, card_id: int) -> UserWord | None:
    card = await session.get(UserWord, card_id)
    return card if card is not None and card.user_id == user.id else None


@router.callback_query(WordCb.filter(F.action == "show"))
async def cb_show(callback: CallbackQuery, callback_data: WordCb, session: AsyncSession, user: User) -> None:
    card = await get_card(session, user, callback_data.card_id)
    if card is None:
        await callback.answer("Карточка не найдена")
        return
    await callback.answer()
    w = card.word
    kb = InlineKeyboardBuilder()
    for text, grade in [("😵 Забыл", Grade.AGAIN), ("😬 С трудом", Grade.HARD),
                        ("🙂 Помню", Grade.GOOD), ("😎 Легко", Grade.EASY)]:
        kb.button(text=text, callback_data=WordCb(action="grade", card_id=card.id, value=int(grade)))
    kb.button(text="🔊", callback_data=WordCb(action="say", card_id=card.id))
    kb.adjust(2, 2, 1)
    await callback.message.edit_text(
        f"<b>{esc(w.en)}</b> — {esc(w.ru)}\n<i>{esc(w.example)}</i>\n\nНасколько легко вспомнил?",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(WordCb.filter(F.action == "grade"))
async def cb_grade(callback: CallbackQuery, callback_data: WordCb, session: AsyncSession,
                   user: User, state: FSMContext) -> None:
    card = await get_card(session, user, callback_data.card_id)
    if card is None:
        await callback.answer("Карточка не найдена")
        return
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    grade = Grade(callback_data.value)
    feedback = "Вернусь к нему через 10 минут 😉" if grade == Grade.AGAIN else "Записал ✍️"
    await register_answer(callback.message, session, user, state, card, grade, feedback)


@router.callback_query(WordCb.filter(F.action == "pick"))
async def cb_pick(callback: CallbackQuery, callback_data: WordCb, session: AsyncSession,
                  user: User, state: FSMContext) -> None:
    data = await state.get_data()
    quiz = data.get("quiz") or {}
    card = await get_card(session, user, callback_data.card_id)
    if card is None or quiz.get("card_id") != card.id:
        await callback.answer("Этот вопрос уже неактуален")
        return
    await state.update_data(quiz=None)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    w = card.word
    if callback_data.value == quiz["correct"]:
        feedback = f"✅ Верно! <b>{esc(w.en)}</b> — {esc(w.ru)}"
        grade = Grade.GOOD
    else:
        feedback = f"❌ Мимо. <b>{esc(w.en)}</b> — {esc(w.ru)}\n<i>{esc(w.example)}</i>"
        grade = Grade.AGAIN
    await register_answer(callback.message, session, user, state, card, grade, feedback)


@router.callback_query(WordCb.filter(F.action == "say"))
async def cb_say(callback: CallbackQuery, callback_data: WordCb, session: AsyncSession,
                 user: User, bot: Bot) -> None:
    card = await get_card(session, user, callback_data.card_id)
    if card is None:
        await callback.answer()
        return
    await callback.answer("Озвучиваю…")
    w = card.word
    # Неправильные глаголы озвучиваем без тире: "go, went, gone"
    text = w.en.replace(" – ", ", ")
    if w.example:
        text += ". " + w.example
    if not await send_speech(bot, callback.message.chat.id, text):
        await callback.message.answer("Озвучка сейчас недоступна 😕")


# ---------- Свои слова ----------

ADD_HINT = (
    "➕ Пришли слова, каждое с новой строки:\n\n"
    "<code>cliffhanger - обрыв на самом интересном месте\n"
    "to binge-watch - смотреть запоем</code>\n\n"
    "/cancel — отмена"
)


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    await state.set_state(AddWords.waiting)
    await message.answer(ADD_HINT)


@router.callback_query(F.data == "words:add")
async def cb_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AddWords.waiting)
    await callback.message.answer(ADD_HINT)


async def save_word_pairs(session: AsyncSession, user: User, pairs: list[tuple[str, str]]) -> tuple[int, int]:
    added = skipped = 0
    for en, ru in pairs:
        _, created = await words_service.add_custom_word(session, user, en, ru)
        added += created
        skipped += not created
    return added, skipped


@router.message(AddWords.waiting, F.text)
async def on_add_words(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    pairs = words_service.parse_word_lines(message.text)
    if not pairs:
        await message.answer("Не понял формат 🤔 Нужно так: <code>word - перевод</code>")
        return
    added, skipped = await save_word_pairs(session, user, pairs)
    await state.clear()
    text = f"✅ Добавил {added} слов в повторение."
    if skipped:
        text += f" ({skipped} уже были у тебя)"
    if added:
        text += "\n" + (await game.award(session, user, added, "custom_words")).text()
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔁 Сразу повторить", callback_data="words:review")]]))
