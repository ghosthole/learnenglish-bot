"""Аудирование: озвученные истории с вопросами, диктант и подборка видео."""
import difflib
import html
import random

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.content.listening import STORIES, STORIES_BY_ID, VIDEO_TIPS
from bot.db.models import User, UserWord, Word
from bot.handlers.grammar import STORY_PREFIX, start_quiz
from bot.keyboards.menu import BTN_LISTENING
from bot.services import gamification as game
from bot.services.checker import normalize
from bot.services.tts import VOICES, send_speech

router = Router()


class Dictation(StatesGroup):
    waiting = State()


@router.message(F.text == BTN_LISTENING)
@router.message(Command("listen"))
async def listening_menu(message: Message) -> None:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎧 Аудиоистория + вопросы", callback_data="ls:story")
    kb.button(text="✍️ Диктант (пиши, что слышишь)", callback_data="ls:dictation")
    kb.button(text="📺 Видео под мой уровень", callback_data="ls:videos")
    kb.adjust(1)
    await message.answer(
        "🎧 <b>Аудирование</b>\n\nСлушай без текста, потом отвечай. "
        "Не понял с первого раза — переслушай, это нормально 👂",
        reply_markup=kb.as_markup(),
    )


# ---------- Истории ----------

async def send_story(message: Message, bot: Bot, state: FSMContext, story_id: str | None = None) -> None:
    data = await state.get_data()
    heard = data.get("stories_heard", [])
    if story_id is None:
        fresh = [s for s in STORIES if s.id not in heard] or STORIES
        story = random.choice(fresh)
    else:
        story = STORIES_BY_ID[story_id]
    await state.update_data(stories_heard=(heard + [story.id])[-len(STORIES):], story_id=story.id)

    await message.answer(f"🎧 <b>{story.title}</b> · {story.level}\nСлушай внимательно, потом будут вопросы.")
    kb = InlineKeyboardBuilder()
    kb.button(text="🐢 Медленнее", callback_data=f"ls:slow:{story.id}")
    kb.button(text="❓ К вопросам", callback_data=f"ls:quiz:{story.id}")
    kb.adjust(2)
    ok = await send_speech(bot, message.chat.id, story.text, voice=random.choice(VOICES),
                           reply_markup=kb.as_markup())
    if not ok:
        # Если озвучка недоступна, даём текст, чтобы задание всё равно можно было сделать
        await message.answer(f"(Озвучка недоступна, вот текст)\n\n<i>{html.escape(story.text)}</i>",
                             reply_markup=kb.as_markup())


@router.callback_query(F.data == "ls:story")
async def cb_story(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    await callback.answer()
    await send_story(callback.message, bot, state)


@router.callback_query(F.data.startswith("ls:slow:"))
async def cb_slow(callback: CallbackQuery, bot: Bot) -> None:
    story = STORIES_BY_ID.get(callback.data.split(":", 2)[2])
    if story is None:
        await callback.answer()
        return
    await callback.answer("Медленная версия…")
    await send_speech(bot, callback.message.chat.id, story.text, rate="-25%")


@router.callback_query(F.data.startswith("ls:quiz:"))
async def cb_story_quiz(callback: CallbackQuery, state: FSMContext) -> None:
    story = STORIES_BY_ID.get(callback.data.split(":", 2)[2])
    if story is None:
        await callback.answer()
        return
    await callback.answer()
    keys = [f"{STORY_PREFIX}{story.id}:{i}" for i in range(len(story.questions))]
    await start_quiz(callback.message, state, keys, mode="listening", lesson=story.id)


async def listening_after_quiz(message: Message, session: AsyncSession, user: User,
                               state: FSMContext, gq: dict) -> None:
    story = STORIES_BY_ID[gq["lesson"]]
    total, correct = len(gq["keys"]), gq["correct"]
    lines = [f"🏁 Понял {correct}/{total} {game.progress_bar(correct, total)}"]
    lines.append((await game.award(session, user, 4 + 3 * correct, "listening")).text())
    if loot := await game.maybe_lootbox(session, user):
        lines.append(loot)
    lines.append(f"\n📜 <b>Текст:</b>\n<tg-spoiler>{html.escape(story.text)}</tg-spoiler>")
    kb = InlineKeyboardBuilder()
    kb.button(text="🎧 Ещё история", callback_data="ls:story")
    kb.button(text="✍️ Диктант", callback_data="ls:dictation")
    kb.adjust(2)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


# ---------- Диктант ----------

async def pick_dictation_sentence(session: AsyncSession, user: User) -> str:
    """Берём пример из слов, которые пользователь сейчас учит, — так диктант ещё и закрепляет лексику."""
    examples = list(await session.scalars(
        select(Word.example).join(UserWord, UserWord.word_id == Word.id)
        .where(UserWord.user_id == user.id, Word.example.is_not(None))
    ))
    if len(examples) < 5:
        examples += list(await session.scalars(
            select(Word.example).where(Word.owner_id.is_(None), Word.example.is_not(None)).limit(100)))
    return random.choice(examples)


async def start_dictation(message: Message, session: AsyncSession, user: User, bot: Bot,
                          state: FSMContext) -> None:
    sentence = await pick_dictation_sentence(session, user)
    await state.set_state(Dictation.waiting)
    await state.update_data(dictation=sentence)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Ещё раз медленно", callback_data="ls:dict_repeat")
    kb.button(text="🏳️ Сдаюсь", callback_data="ls:dict_giveup")
    ok = await send_speech(bot, message.chat.id, sentence, voice=random.choice(VOICES),
                           caption="✍️ Напиши, что услышал", reply_markup=kb.as_markup())
    if not ok:
        await state.set_state(None)
        await message.answer("Озвучка сейчас недоступна 😕 Попробуй позже.")


@router.callback_query(F.data == "ls:dictation")
async def cb_dictation(callback: CallbackQuery, session: AsyncSession, user: User, bot: Bot,
                       state: FSMContext) -> None:
    await callback.answer()
    await start_dictation(callback.message, session, user, bot, state)


@router.callback_query(F.data == "ls:dict_repeat")
async def cb_dict_repeat(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    sentence = (await state.get_data()).get("dictation")
    await callback.answer()
    if sentence:
        await send_speech(bot, callback.message.chat.id, sentence, rate="-30%")


@router.callback_query(F.data == "ls:dict_giveup")
async def cb_dict_giveup(callback: CallbackQuery, state: FSMContext) -> None:
    sentence = (await state.get_data()).get("dictation")
    await callback.answer()
    await state.set_state(None)
    if sentence:
        kb = InlineKeyboardBuilder()
        kb.button(text="✍️ Следующий", callback_data="ls:dictation")
        await callback.message.answer(f"Было: <b>{html.escape(sentence)}</b>\nНичего, в следующий раз 💪",
                                      reply_markup=kb.as_markup())


def diff_hint(expected: str, answer: str) -> str:
    """Подсвечивает слова, в которых ошибка: ~~твоё~~ → правильное."""
    exp_words, ans_words = normalize(expected).split(), normalize(answer).split()
    parts = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ans_words, b=exp_words).get_opcodes():
        if op == "equal":
            parts.append(" ".join(ans_words[i1:i2]))
        else:
            if i2 > i1:
                parts.append("<s>" + html.escape(" ".join(ans_words[i1:i2])) + "</s>")
            if j2 > j1:
                parts.append("<b>" + html.escape(" ".join(exp_words[j1:j2])) + "</b>")
    return " ".join(parts)


@router.message(Dictation.waiting, F.text)
async def on_dictation(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    sentence = (await state.get_data()).get("dictation", "")
    await state.set_state(None)
    ratio = difflib.SequenceMatcher(a=normalize(sentence), b=normalize(message.text)).ratio()
    if ratio == 1:
        text = "✅ Идеально! Слово в слово 🎯"
        xp = 6
    elif ratio >= 0.85:
        text = f"🟡 Почти! Мелкие ошибки:\n{diff_hint(sentence, message.text)}"
        xp = 3
    else:
        text = f"❌ Правильно так:\n<b>{html.escape(sentence)}</b>\n\nТвои отличия: {diff_hint(sentence, message.text)}"
        xp = 1
    text += "\n" + (await game.award(session, user, xp, "dictation")).text()
    kb = InlineKeyboardBuilder()
    kb.button(text="✍️ Следующий", callback_data="ls:dictation")
    await message.answer(text, reply_markup=kb.as_markup())


# ---------- Видео ----------

@router.callback_query(F.data == "ls:videos")
async def cb_videos(callback: CallbackQuery) -> None:
    await callback.answer()
    lines = ["📺 <b>Видео под твой уровень</b>\n"]
    for tip in VIDEO_TIPS:
        lines.append(f'• <a href="{tip.url}">{html.escape(tip.title)}</a>\n   {html.escape(tip.why)}')
    lines.append(
        "\n💡 Как смотреть эффективно:\n"
        "1. Первый раз — с английскими субтитрами\n"
        "2. Незнакомые слова выписывай и кидай мне через /add\n"
        "3. Любимую сцену пересмотри без субтитров\n\n"
        "За просмотр есть квесты с очками → 🎯 Квесты"
    )
    await callback.message.answer("\n".join(lines), disable_web_page_preview=True)
