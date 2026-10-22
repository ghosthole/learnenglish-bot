"""Грамматика: теория, практика, работа над ошибками.

Вопросы задаются «по ключу» вида "lesson_id:номер_вопроса". Один и тот же
механизм используется в уроках, в работе над ошибками, в 5-минутке и в проверках.
"""
import html
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.content.grammar import LESSONS, LESSONS_BY_ID, Question
from bot.content.sentences import TR_PREFIX, TRANSLATIONS, translation_keys
from bot.db.models import GrammarProgress, Mistake, User
from bot.keyboards.menu import BTN_GRAMMAR
from bot.services import gamification as game
from bot.services import practice
from bot.services.checker import check_answer
from bot.services.timeutils import utcnow

router = Router()

PASS_SCORE = 70  # процент правильных, чтобы урок считался пройденным
LESSON_EXTRA_TRANSLATIONS = 2  # сколько свежих предложений из банка добавлять к практике урока


class GrCb(CallbackData, prefix="g"):
    action: str  # open | practice | ans | menu | mistakes | accept
    # для accept здесь ключ вопроса, где ":" заменено на "~" (двоеточие — разделитель в callback_data)
    lesson: str = ""
    value: int = 0


class GrammarQuiz(StatesGroup):
    answering = State()


STORY_PREFIX = "story."  # ключи вопросов к аудиоисториям: "story.rainy_day:0"


def get_question(key: str) -> tuple[str, Question]:
    source_id, idx = key.rsplit(":", 1)
    if source_id.startswith(STORY_PREFIX):
        from bot.content.listening import STORIES_BY_ID
        return source_id, STORIES_BY_ID[source_id.removeprefix(STORY_PREFIX)].questions[int(idx)]
    if source_id.startswith(TR_PREFIX):
        return source_id, TRANSLATIONS[source_id.removeprefix(TR_PREFIX)][int(idx)]
    return source_id, LESSONS_BY_ID[source_id].questions[int(idx)]


def lesson_id_of(source_id: str) -> str:
    """"tr.present_simple" → "present_simple"; для обычных уроков id не меняется."""
    return source_id.removeprefix(TR_PREFIX)


def is_grammar_key(key: str) -> bool:
    """Ключ существующего вопроса из урока или банка переводов (контент мог поменяться)."""
    source_id, idx = key.rsplit(":", 1)
    if source_id.startswith(TR_PREFIX):
        return int(idx) < len(TRANSLATIONS.get(lesson_id_of(source_id), []))
    lesson = LESSONS_BY_ID.get(source_id)
    return lesson is not None and int(idx) < len(lesson.questions)


def lesson_keys(lesson_id: str) -> list[str]:
    return [f"{lesson_id}:{i}" for i in range(len(LESSONS_BY_ID[lesson_id].questions))]


# ---------- Меню ----------

async def progress_map(session: AsyncSession, user: User) -> dict[str, GrammarProgress]:
    rows = await session.scalars(select(GrammarProgress).where(GrammarProgress.user_id == user.id))
    return {p.lesson_id: p for p in rows}


async def open_mistakes_count(session: AsyncSession, user: User) -> int:
    return await session.scalar(
        select(func.count()).select_from(Mistake).where(Mistake.user_id == user.id, Mistake.fixed.is_(False))
    ) or 0


def next_lesson_id(progress: dict[str, GrammarProgress]) -> str | None:
    for lesson in LESSONS:
        p = progress.get(lesson.id)
        if p is None or p.best_score < PASS_SCORE:
            return lesson.id
    return None


async def send_grammar_menu(message: Message, session: AsyncSession, user: User) -> None:
    progress = await progress_map(session, user)
    recommended = next_lesson_id(progress)
    passed = sum(1 for p in progress.values() if p.best_score >= PASS_SCORE)

    kb = InlineKeyboardBuilder()
    for lesson in LESSONS:
        p = progress.get(lesson.id)
        if p and p.best_score >= PASS_SCORE:
            mark = "✅"
        elif lesson.id == recommended:
            mark = "👉"
        elif p:
            mark = "🟡"
        else:
            mark = "▫️"
        kb.button(text=f"{mark} {lesson.title}", callback_data=GrCb(action="open", lesson=lesson.id))
    mistakes = await open_mistakes_count(session, user)
    if mistakes:
        kb.button(text=f"🔁 Работа над ошибками ({mistakes})", callback_data=GrCb(action="mistakes"))
    kb.adjust(1)
    await message.answer(
        f"📖 <b>Грамматика</b>\nПройдено: {passed}/{len(LESSONS)} {game.progress_bar(passed, len(LESSONS))}\n\n"
        "👉 — рекомендую следующим. Уроки идут от твоих слабых мест к уровню B1.",
        reply_markup=kb.as_markup(),
    )


@router.message(F.text == BTN_GRAMMAR)
@router.message(Command("grammar"))
async def grammar_menu(message: Message, session: AsyncSession, user: User) -> None:
    await send_grammar_menu(message, session, user)


@router.callback_query(GrCb.filter(F.action == "menu"))
async def cb_menu(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    await callback.answer()
    await send_grammar_menu(callback.message, session, user)


@router.callback_query(GrCb.filter(F.action == "open"))
async def cb_open(callback: CallbackQuery, callback_data: GrCb) -> None:
    lesson = LESSONS_BY_ID.get(callback_data.lesson)
    if lesson is None:
        await callback.answer("Урок не найден")
        return
    await callback.answer()
    kb = InlineKeyboardBuilder()
    total = len(lesson.questions) + min(LESSON_EXTRA_TRANSLATIONS, len(TRANSLATIONS.get(lesson.id, [])))
    kb.button(text=f"💪 К практике ({total} вопросов)",
              callback_data=GrCb(action="practice", lesson=lesson.id))
    kb.button(text="⬅️ К урокам", callback_data=GrCb(action="menu"))
    kb.adjust(1)
    await callback.message.answer(f"<b>{lesson.title}</b>\n\n{lesson.theory}", reply_markup=kb.as_markup())


# ---------- Общий механизм вопросов ----------

async def start_quiz(message: Message, state: FSMContext, keys: list[str], mode: str, lesson: str = "") -> None:
    """mode: lesson | mistakes | sprint | check | listening"""
    await state.update_data(gq={"keys": keys, "idx": 0, "correct": 0, "mode": mode, "lesson": lesson,
                                "wrong": []})
    await ask_current(message, state)


async def ask_current(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    gq = data["gq"]
    key = gq["keys"][gq["idx"]]
    _, q = get_question(key)
    total = len(gq["keys"])
    header = f"<b>{gq['idx'] + 1}/{total}</b> " if total > 1 else ""

    if q.kind == "choice":
        await state.set_state(None)
        kb = InlineKeyboardBuilder()
        for i, opt in enumerate(q.options):
            kb.button(text=opt, callback_data=GrCb(action="ans", value=i))
        kb.adjust(len(q.options) if all(len(o) < 12 for o in q.options) else 1)
        await message.answer(f"{header}{html.escape(q.prompt)}", reply_markup=kb.as_markup())
    else:
        await state.set_state(GrammarQuiz.answering)
        await message.answer(f"{header}✍️ {html.escape(q.prompt)}\n\n<i>Напиши ответ сообщением</i>")


async def record_result(session: AsyncSession, user: User, key: str, ok: bool, mode: str) -> None:
    source_id, _ = get_question(key)
    await practice.mark_seen(session, user, key)
    if source_id.startswith(STORY_PREFIX):
        return  # ошибки в аудировании в «Работу над ошибками» не попадают
    mistake = await session.scalar(select(Mistake).where(Mistake.user_id == user.id, Mistake.item_key == key))
    if not ok:
        if mistake is None:
            topic = LESSONS_BY_ID[lesson_id_of(source_id)].weak_spot
            session.add(Mistake(user_id=user.id, item_key=key, topic=topic))
        else:
            mistake.times_wrong += 1
            mistake.fixed = False
            mistake.updated_at = utcnow()
    elif mistake is not None and mode in ("mistakes", "sprint", "check"):
        mistake.fixed = True
        mistake.updated_at = utcnow()
    await session.flush()


async def handle_answer(
    message: Message, session: AsyncSession, user: User, state: FSMContext, ok: bool, comment: str = ""
) -> None:
    data = await state.get_data()
    gq = data["gq"]
    key = gq["keys"][gq["idx"]]
    _, q = get_question(key)
    await record_result(session, user, key, ok, gq["mode"])

    if ok:
        gq["correct"] += 1
        text = random.choice(["✅ Yes!", "✅ Точно!", "✅ Nailed it 💅", "✅ Изи", "✅ Correct!"])
    else:
        gq["wrong"].append(key)
        correct = q.options[q.answer] if q.kind == "choice" else q.answers[0]
        text = f"❌ Правильно: <b>{html.escape(correct)}</b>"
    text += f"\n<i>{q.explain}</i>"
    if comment:
        text += f"\n\n🤖 {html.escape(comment)}"
    kb = None
    if not ok and q.kind == "text":
        # Проверка без ИИ сравнивает с готовыми вариантами и может не знать твой верный вариант
        kb = InlineKeyboardBuilder()
        kb.button(text="🙋 Мой вариант тоже верный", callback_data=GrCb(action="accept", lesson=key.replace(":", "~")))
        kb = kb.as_markup()
    await message.answer(text, reply_markup=kb)

    gq["idx"] += 1
    await state.update_data(gq=gq)
    if gq["idx"] < len(gq["keys"]):
        await ask_current(message, state)
    else:
        await finish_quiz(message, session, user, state)


async def finish_quiz(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    await state.set_state(None)
    data = await state.get_data()
    gq = data["gq"]
    mode = gq["mode"]

    if mode == "sprint":
        from bot.handlers.sprint import sprint_after_grammar
        await sprint_after_grammar(message, session, user, state, gq["correct"])
        return
    if mode == "listening":
        from bot.handlers.listening import listening_after_quiz
        await listening_after_quiz(message, session, user, state, gq)
        return
    if mode == "check":
        from bot.handlers.check import check_after_grammar
        await check_after_grammar(message, session, user, state, gq)
        return

    total, correct = len(gq["keys"]), gq["correct"]
    score = round(100 * correct / total)
    lines = [f"🏁 <b>{correct}/{total}</b> ({score}%) {game.progress_bar(correct, total)}"]

    if mode == "lesson":
        lesson_id = gq["lesson"]
        progress = await session.scalar(select(GrammarProgress).where(
            GrammarProgress.user_id == user.id, GrammarProgress.lesson_id == lesson_id))
        first_pass = progress is None or progress.best_score < PASS_SCORE
        if progress is None:
            progress = GrammarProgress(user_id=user.id, lesson_id=lesson_id, best_score=0, attempts=0)
            session.add(progress)
        progress.attempts += 1
        progress.best_score = max(progress.best_score, score)
        if score >= PASS_SCORE and progress.completed_at is None:
            progress.completed_at = utcnow()
        await session.flush()

        xp = 5 + 2 * correct + (10 if score == 100 else 0) + (10 if first_pass and score >= PASS_SCORE else 0)
        lines.append("Урок пройден! 🎉" if score >= PASS_SCORE else
                     f"Чтобы засчитать урок, нужно {PASS_SCORE}%. Ошибки ушли в «Работу над ошибками» 🔁")
        lines.append((await game.award(session, user, xp, "grammar")).text())
    else:  # mistakes
        lines.append("Исправленные ошибки больше не будут попадаться 💪")
        lines.append((await game.award(session, user, 3 + 2 * correct, "mistakes")).text())

    if loot := await game.maybe_lootbox(session, user):
        lines.append(loot)

    kb = InlineKeyboardBuilder()
    if gq["wrong"] and mode == "lesson":
        kb.button(text="🔁 Перерешать ошибки", callback_data=GrCb(action="mistakes"))
    kb.button(text="📖 К урокам", callback_data=GrCb(action="menu"))
    kb.adjust(1)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


@router.callback_query(GrCb.filter(F.action == "practice"))
async def cb_practice(callback: CallbackQuery, callback_data: GrCb, session: AsyncSession,
                      user: User, state: FSMContext) -> None:
    if callback_data.lesson not in LESSONS_BY_ID:
        await callback.answer("Урок не найден")
        return
    await callback.answer()
    # Вопросы урока + пара свежих предложений на перевод, чтобы при повторе было что-то новое
    keys = lesson_keys(callback_data.lesson) + await practice.pick_fresh(
        session, user, translation_keys(callback_data.lesson), LESSON_EXTRA_TRANSLATIONS)
    random.shuffle(keys)
    await start_quiz(callback.message, state, keys, mode="lesson", lesson=callback_data.lesson)


@router.callback_query(GrCb.filter(F.action == "mistakes"))
async def cb_mistakes(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext) -> None:
    rows = list(await session.scalars(
        select(Mistake.item_key).where(Mistake.user_id == user.id, Mistake.fixed.is_(False))
        .order_by(Mistake.times_wrong.desc(), Mistake.updated_at).limit(8)
    ))
    keys = [k for k in rows if is_grammar_key(k)]
    await callback.answer()
    if not keys:
        await callback.message.answer("Ошибок нет, ты чист 😇")
        return
    await callback.message.answer("🔁 <b>Работа над ошибками</b>\nТолько то, где ты уже ошибался. Реванш!")
    await start_quiz(callback.message, state, keys, mode="mistakes")


@router.callback_query(GrCb.filter(F.action == "ans"))
async def cb_answer(callback: CallbackQuery, callback_data: GrCb, session: AsyncSession,
                    user: User, state: FSMContext) -> None:
    data = await state.get_data()
    gq = data.get("gq")
    if not gq or gq["idx"] >= len(gq["keys"]):
        await callback.answer("Этот вопрос уже неактуален")
        return
    _, q = get_question(gq["keys"][gq["idx"]])
    if q.kind != "choice":
        await callback.answer("Этот вопрос уже неактуален")
        return
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await handle_answer(callback.message, session, user, state, ok=callback_data.value == q.answer)


@router.message(GrammarQuiz.answering, F.text)
async def on_text_answer(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    data = await state.get_data()
    gq = data.get("gq")
    if not gq:
        await state.clear()
        return
    _, q = get_question(gq["keys"][gq["idx"]])
    await message.bot.send_chat_action(message.chat.id, "typing")
    result = await check_answer(message.text, q.answers, task=q.prompt)
    await handle_answer(message, session, user, state, ok=result.ok, comment=result.comment)


@router.callback_query(GrCb.filter(F.action == "accept"))
async def cb_accept(callback: CallbackQuery, callback_data: GrCb, session: AsyncSession, user: User) -> None:
    """Пользователь уверен, что его перевод верный: убираем вопрос из «Работы над ошибками»."""
    mistake = await session.scalar(
        select(Mistake).where(Mistake.user_id == user.id, Mistake.item_key == callback_data.lesson.replace("~", ":")))
    if mistake is not None:
        mistake.fixed = True
        mistake.updated_at = utcnow()
    await callback.answer("Ок, засчитал 👍 В ошибки не пойдёт")
    await callback.message.edit_reply_markup(reply_markup=None)
