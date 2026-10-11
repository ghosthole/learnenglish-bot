"""Квесты: каждый день три задания (small / medium / big) за очки."""
import random
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.content.quests import QUESTS, QUESTS_BY_ID, Quest
from bot.db.models import User, UserQuest
from bot.handlers.words import save_word_pairs
from bot.keyboards.menu import BTN_QUESTS
from bot.services import gamification as game
from bot.services import llm
from bot.services.timeutils import user_today, utcnow
from bot.services.words import parse_word_lines

router = Router()

SIZES = ["small", "medium", "big"]
SIZE_ICONS = {"small": "🟢", "medium": "🟡", "big": "🔴"}
REROLLS_PER_DAY = 1


class QuestCb(CallbackData, prefix="q"):
    action: str  # open | submit | reroll | list
    uq_id: int = 0


class QuestSubmit(StatesGroup):
    waiting = State()


async def todays_quests(session: AsyncSession, user: User) -> list[UserQuest]:
    """Квесты на сегодня. Если их ещё нет — выдаём по одному каждого размера."""
    today = user_today(user)
    rows = list(await session.scalars(
        select(UserQuest).where(UserQuest.user_id == user.id, UserQuest.assigned_on == today)
        .order_by(UserQuest.id)
    ))
    if rows:
        return rows

    # Не повторяем квесты последних дней, если есть из чего выбрать
    recent = set(await session.scalars(
        select(UserQuest.quest_id).where(UserQuest.user_id == user.id).order_by(UserQuest.id.desc()).limit(9)
    ))
    for size in SIZES:
        pool = [q for q in QUESTS if q.size == size]
        fresh = [q for q in pool if q.id not in recent] or pool
        session.add(UserQuest(user_id=user.id, quest_id=random.choice(fresh).id, assigned_on=today))
    await session.flush()
    return await todays_quests(session, user)


def quest_status_icon(uq: UserQuest) -> str:
    return {"done": "✅", "skipped": "⏭"}.get(uq.status, SIZE_ICONS[QUESTS_BY_ID[uq.quest_id].size])


async def send_quests_menu(message: Message, session: AsyncSession, user: User) -> None:
    rows = await todays_quests(session, user)
    visible = [uq for uq in rows if uq.status != "skipped"]
    rerolls_used = sum(1 for uq in rows if uq.status == "skipped")

    lines = ["🎯 <b>Квесты на сегодня</b>\n"]
    kb = InlineKeyboardBuilder()
    for uq in visible:
        q = QUESTS_BY_ID[uq.quest_id]
        lines.append(f"{quest_status_icon(uq)} {q.title} — <b>{q.xp} XP</b>")
        if uq.status == "active":
            kb.button(text=f"▶️ {q.title}", callback_data=QuestCb(action="open", uq_id=uq.id))
    if any(uq.status == "active" for uq in visible) and rerolls_used < REROLLS_PER_DAY:
        kb.button(text="🎲 Заменить один квест", callback_data=QuestCb(action="reroll"))
    kb.adjust(1)
    if all(uq.status == "done" for uq in visible):
        lines.append("\n🏆 Все квесты на сегодня закрыты. Легенда!")
    else:
        lines.append("\n🟢 лёгкий · 🟡 средний · 🔴 большой\nКвесты обновляются каждый день.")
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


@router.message(F.text == BTN_QUESTS)
@router.message(Command("quests"))
async def quests_menu(message: Message, session: AsyncSession, user: User) -> None:
    await send_quests_menu(message, session, user)


@router.callback_query(QuestCb.filter(F.action == "list"))
async def cb_list(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    await callback.answer()
    await send_quests_menu(callback.message, session, user)


async def get_user_quest(session: AsyncSession, user: User, uq_id: int) -> UserQuest | None:
    uq = await session.get(UserQuest, uq_id)
    return uq if uq is not None and uq.user_id == user.id else None


@router.callback_query(QuestCb.filter(F.action == "open"))
async def cb_open(callback: CallbackQuery, callback_data: QuestCb, session: AsyncSession,
                  user: User, state: FSMContext) -> None:
    uq = await get_user_quest(session, user, callback_data.uq_id)
    if uq is None or uq.status != "active":
        await callback.answer("Квест уже неактуален")
        return
    await callback.answer()
    q = QUESTS_BY_ID[uq.quest_id]
    await state.set_state(QuestSubmit.waiting)
    await state.update_data(quest_uq_id=uq.id)
    how = {"words": "📤 Пришли список слов сообщением",
           "text": "📤 Пришли текст сообщением",
           "voice": "📤 Пришли голосовое",
           "any": "📤 Пришли текст или голосовое"}[q.submit]
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ К квестам", callback_data=QuestCb(action="list"))
    await callback.message.answer(
        f"{SIZE_ICONS[q.size]} <b>{q.title}</b> · {q.xp} XP\n\n{q.description}\n\n{how}\n"
        "Можно сделать позже — просто открой квест снова.",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(QuestCb.filter(F.action == "reroll"))
async def cb_reroll(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    rows = await todays_quests(session, user)
    if sum(1 for uq in rows if uq.status == "skipped") >= REROLLS_PER_DAY:
        await callback.answer("Замена на сегодня уже использована")
        return
    active = [uq for uq in rows if uq.status == "active"]
    if not active:
        await callback.answer("Нечего заменять")
        return
    await callback.answer("🎲 Кидаю кубик…")
    old = random.choice(active)
    old.status = "skipped"
    size = QUESTS_BY_ID[old.quest_id].size
    taken = {uq.quest_id for uq in rows}
    pool = [q for q in QUESTS if q.size == size and q.id not in taken] or [q for q in QUESTS if q.size == size]
    session.add(UserQuest(user_id=user.id, quest_id=random.choice(pool).id, assigned_on=user_today(user)))
    await session.flush()
    await send_quests_menu(callback.message, session, user)


def count_sentences(text: str) -> int:
    return len([s for s in re.split(r"[.!?\n]+", text) if len(s.split()) >= 3])


async def complete_quest(message: Message, session: AsyncSession, user: User,
                         uq: UserQuest, q: Quest, submission: str, extra: str = "") -> None:
    uq.status = "done"
    uq.completed_at = utcnow()
    uq.submission = submission[:4000]
    uq.xp_awarded = q.xp
    await session.flush()
    lines = [f"🎯 Квест «{q.title}» выполнен!"]
    if extra:
        lines.append(extra)
    lines.append((await game.award(session, user, q.xp, f"quest:{q.id}")).text())
    if loot := await game.maybe_lootbox(session, user, chance=0.35):
        lines.append(loot)
    kb = InlineKeyboardBuilder()
    kb.button(text="🎯 К квестам", callback_data=QuestCb(action="list"))
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


@router.message(QuestSubmit.waiting, F.text | F.voice | F.video_note)
async def on_submission(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    uq = await get_user_quest(session, user, (await state.get_data()).get("quest_uq_id", 0))
    if uq is None or uq.status != "active":
        await state.set_state(None)
        await message.answer("Этот квест уже закрыт. Открой список квестов 🎯")
        return
    q = QUESTS_BY_ID[uq.quest_id]
    is_voice = message.voice is not None or message.video_note is not None

    if q.submit == "voice" and not is_voice:
        await message.answer("Этот квест сдаётся голосовым 🎤")
        return
    if q.submit in ("words", "text") and is_voice:
        await message.answer("Тут нужен текст ✍️")
        return

    if is_voice:
        duration = (message.voice or message.video_note).duration
        if duration < 5:
            await message.answer("Коротковато 😅 Давай хотя бы 5 секунд.")
            return
        await state.set_state(None)
        await complete_quest(message, session, user, uq, q, f"voice:{duration}s",
                             "🔥 Говорить вслух — самый недооценённый навык. Респект!")
        return

    if q.submit == "words":
        pairs = parse_word_lines(message.text)
        if len(pairs) < q.min_items:
            await message.answer(f"Нашёл {len(pairs)} из {q.min_items} строк вида <code>word - перевод</code>. "
                                 "Добавь ещё и пришли весь список заново.")
            return
        added, _ = await save_word_pairs(session, user, pairs)
        await state.set_state(None)
        await complete_quest(message, session, user, uq, q, message.text,
                             f"📚 {added} новых слов добавлено в повторение.")
        return

    # text / any
    if count_sentences(message.text) < max(q.min_items, 1):
        await message.answer(f"Нужно минимум {q.min_items} предложений (по 3+ слова). Допиши и пришли целиком.")
        return
    await state.set_state(None)
    extra = ""
    if llm.enabled():
        await message.bot.send_chat_action(message.chat.id, "typing")
        feedback = await llm.review_writing(task=q.description, text=message.text)
        if feedback:
            extra = f"🤖 <b>Разбор:</b>\n{feedback}"
    else:
        extra = ("🔍 Самопроверка: перечитай и проверь три вещи — "
                 "-s у he/she/it, прошедшее время глаголов, артикли a/the.")
    await complete_quest(message, session, user, uq, q, message.text, extra)
