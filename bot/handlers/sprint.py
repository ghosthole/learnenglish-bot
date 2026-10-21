"""⚡ 5-минутка: короткий микс из слов, грамматики и брейн-брейков.

Порядок заданий хранится в FSM: state data["sprint"]["queue"]. После каждого
задания модули слов и грамматики вызывают sprint_next(), и мы берём следующее.
"""
import random
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.content.fun import BRAIN_BREAKS
from bot.content.grammar import LESSONS, LESSONS_BY_ID
from bot.content.sentences import translation_keys
from bot.db.models import GrammarProgress, Mistake, User
from bot.handlers.grammar import is_grammar_key, lesson_keys, start_quiz
from bot.handlers.words import esc, send_card
from bot.keyboards.menu import BTN_SPRINT
from bot.services import gamification as game
from bot.services import practice
from bot.services import words as words_service

router = Router()

SPRINT_PLAN = ["word", "word", "grammar", "word", "fact", "word", "grammar", "word", "word", "grammar"]
FAST_SECONDS = 5 * 60


MISTAKE_COOLDOWN_HOURS = 12  # ошибку, которую только что видел, повторно не даём
TRANSLATION_SHARE = 0.5  # доля предложений на перевод среди новых грамматических заданий


async def pick_grammar_key(session: AsyncSession, user: User, used: set[str]) -> str:
    """Сначала — старые ошибки (кроме недавно показанных), потом — свежие вопросы
    и предложения на перевод из уже начатых уроков, иначе — из первых уроков."""
    mistakes = [k for k in await session.scalars(
        select(Mistake.item_key).where(Mistake.user_id == user.id, Mistake.fixed.is_(False))
    ) if is_grammar_key(k) and k not in used]
    if mistakes:
        mistakes = [k for k in mistakes if k not in await practice.seen_recently(
            session, user, mistakes, MISTAKE_COOLDOWN_HOURS)]
    if mistakes and random.random() < 0.4:
        return random.choice(mistakes)

    started = list(await session.scalars(
        select(GrammarProgress.lesson_id).where(GrammarProgress.user_id == user.id)))
    lesson_ids = [lid for lid in started if lid in LESSONS_BY_ID]
    if not lesson_ids:
        lesson_ids = [lesson.id for lesson in LESSONS[:3]]
    if random.random() < TRANSLATION_SHARE:
        candidates = [k for lid in lesson_ids for k in translation_keys(lid)]
    else:
        candidates = [k for lid in lesson_ids for k in lesson_keys(lid)]
    picked = await practice.pick_fresh(session, user, candidates, 1, exclude=used)
    return picked[0] if picked else random.choice(candidates)


async def start_sprint(message: Message, state: FSMContext) -> None:
    await state.set_state(None)
    await state.update_data(
        sprint={"queue": list(SPRINT_PLAN), "started": time.time(), "correct": 0, "used": []},
        review_done=0, review_correct=0, combo=0,
    )
    await message.answer("⚡ <b>5-минутка!</b> 10 быстрых заданий. Успеешь за 5 минут — бонус x2 🏎")


@router.message(F.text == BTN_SPRINT)
@router.message(Command("sprint"))
async def cmd_sprint(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    await start_sprint(message, state)
    await sprint_next(message, session, user, state)


@router.callback_query(F.data == "sprint:start")
async def cb_sprint(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext) -> None:
    await callback.answer()
    await start_sprint(callback.message, state)
    await sprint_next(callback.message, session, user, state)


@router.callback_query(F.data == "sprint:next")
async def cb_next(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    if not (await state.get_data()).get("sprint"):
        return
    await sprint_next(callback.message, session, user, state)


async def sprint_next(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    data = await state.get_data()
    sprint = data.get("sprint")
    if not sprint:
        return
    if not sprint["queue"]:
        await finish_sprint(message, session, user, state)
        return

    item = sprint["queue"].pop(0)
    await state.update_data(sprint=sprint)

    if item == "word":
        cards = await words_service.get_due_cards(session, user, limit=1)
        if not cards:
            new_words = await words_service.pick_new_words(session, user, 1)
            if not new_words:
                await sprint_next(message, session, user, state)
                return
            cards = await words_service.start_learning(session, user, new_words)
            w = cards[0].word = new_words[0]
            await message.answer(f"✨ Новое слово: <b>{esc(w.en)}</b> — {esc(w.ru)}\n<i>{esc(w.example)}</i>")
        await send_card(message, session, state, cards[0])
    elif item == "grammar":
        key = await pick_grammar_key(session, user, set(sprint.get("used", [])))
        sprint.setdefault("used", []).append(key)
        await state.update_data(sprint=sprint)
        await start_quiz(message, state, [key], mode="sprint")
    else:  # fact
        kb = InlineKeyboardBuilder()
        kb.button(text="➡️ Дальше", callback_data="sprint:next")
        await message.answer(random.choice(BRAIN_BREAKS), reply_markup=kb.as_markup())


async def sprint_after_grammar(message: Message, session: AsyncSession, user: User,
                               state: FSMContext, correct: int) -> None:
    data = await state.get_data()
    sprint = data.get("sprint")
    if sprint:
        sprint["correct"] += correct
        await state.update_data(sprint=sprint)
        if correct:
            await game.award(session, user, 3, "sprint_grammar")
    await sprint_next(message, session, user, state)


async def finish_sprint(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    data = await state.get_data()
    sprint = data["sprint"]
    elapsed = int(time.time() - sprint["started"])
    correct = sprint["correct"] + data.get("review_correct", 0)
    await state.update_data(sprint=None, review_done=0, review_correct=0, combo=0)

    bonus = 10
    lines = [f"🏁 <b>5-минутка закрыта!</b> Время: {elapsed // 60}:{elapsed % 60:02d} · верно: {correct}"]
    if elapsed <= FAST_SECONDS:
        bonus *= 2
        lines.append("🏎 Уложился в 5 минут — бонус x2!")
    lines.append((await game.award(session, user, bonus, "sprint")).text())
    if loot := await game.maybe_lootbox(session, user, chance=0.3):
        lines.append(loot)

    today = await game.daily_xp(session, user)
    lines.append(f"\nСегодня: {today}/{user.daily_goal_xp} XP {game.progress_bar(today, user.daily_goal_xp)}")
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Ещё одну", callback_data="sprint:start")
    kb.button(text="🎯 Квесты", callback_data="q:list:0")
    kb.adjust(2)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())
