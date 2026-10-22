"""🧪 Проверка знаний: еженедельная контрольная по грамматике и словам.

Результаты сохраняются в test_results, по ним видно рост и слабые места.
"""
import html
import json
import random
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.content.grammar import LESSONS, LESSONS_BY_ID, WEAK_SPOT_NAMES
from bot.db.models import Mistake, TestResult, User, UserWord, Word
from bot.content.sentences import translation_keys
from bot.handlers.grammar import get_question, is_grammar_key, lesson_id_of, lesson_keys, start_quiz
from bot.keyboards.menu import BTN_CHECK
from bot.services import gamification as game
from bot.services.checker import normalize
from bot.services.timeutils import user_tz, utcnow

router = Router()

GRAMMAR_QUESTIONS = 8
VOCAB_QUESTIONS = 5


class CheckVocab(StatesGroup):
    answering = State()


@router.message(F.text == BTN_CHECK)
@router.message(Command("check"))
async def check_menu(message: Message, session: AsyncSession, user: User) -> None:
    results = list(await session.scalars(
        select(TestResult).where(TestResult.user_id == user.id, TestResult.kind == "weekly")
        .order_by(TestResult.created_at.desc()).limit(5)))
    lines = ["🧪 <b>Проверка знаний</b>\n",
             f"{GRAMMAR_QUESTIONS} вопросов по грамматике + {VOCAB_QUESTIONS} слов на перевод. "
             "Без подсказок, как на экзамене. Лучше проходить раз в неделю — так виден рост 📈"]
    if results:
        lines.append("\n<b>Последние результаты:</b>")
        for r in results:
            day = r.created_at.astimezone(user_tz(user)).strftime("%d.%m")
            pct = round(100 * r.score / r.total)
            lines.append(f"{day}: {r.score}/{r.total} ({pct}%) {game.progress_bar(r.score, r.total)}")
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Начать проверку", callback_data="check:start")
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


async def pick_check_keys(session: AsyncSession, user: User) -> list[str]:
    """Вопросы из всех слабых мест: половина — где уже были ошибки, остальное — случайно."""
    mistakes = [k for k in await session.scalars(
        select(Mistake.item_key).where(Mistake.user_id == user.id)) if is_grammar_key(k)]
    random.shuffle(mistakes)
    keys = mistakes[: GRAMMAR_QUESTIONS // 2]

    by_spot: dict[str, list[str]] = {}
    for lesson in LESSONS:
        by_spot.setdefault(lesson.weak_spot, []).extend(lesson_keys(lesson.id) + translation_keys(lesson.id))
    spots = list(by_spot)
    i = 0
    while len(keys) < GRAMMAR_QUESTIONS:
        candidates = [k for k in by_spot[spots[i % len(spots)]] if k not in keys]
        if candidates:
            keys.append(random.choice(candidates))
        i += 1
    random.shuffle(keys)
    return keys


@router.callback_query(F.data == "check:start")
async def cb_start(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer("🧪 Часть 1 — грамматика. Погнали!")
    await start_quiz(callback.message, state, await pick_check_keys(session, user), mode="check")


async def check_after_grammar(message: Message, session: AsyncSession, user: User,
                              state: FSMContext, gq: dict) -> None:
    """Вызывается из grammar.finish_quiz после грамматической части."""
    cards = list(await session.scalars(
        select(UserWord).where(UserWord.user_id == user.id, UserWord.repetitions >= 1)))
    random.shuffle(cards)
    word_ids = [c.word_id for c in cards[:VOCAB_QUESTIONS]]
    await state.update_data(check={"grammar_keys": gq["keys"], "grammar_wrong": gq["wrong"],
                                   "grammar_correct": gq["correct"], "word_ids": word_ids,
                                   "vocab_idx": 0, "vocab_correct": 0, "vocab_wrong": []})
    if not word_ids:
        await finish_check(message, session, user, state)
        return
    await message.answer("🧪 Часть 2 — слова. Напиши перевод на английский.")
    await ask_vocab(message, session, state)


async def ask_vocab(message: Message, session: AsyncSession, state: FSMContext) -> None:
    check = (await state.get_data())["check"]
    word = await session.get(Word, check["word_ids"][check["vocab_idx"]])
    await state.set_state(CheckVocab.answering)
    await message.answer(f"<b>{check['vocab_idx'] + 1}/{len(check['word_ids'])}</b> ✍️ {html.escape(word.ru)}")


def accepted_forms(en: str) -> set[str]:
    """«to book» → {"to book", "book"}; «go – went – gone» → {"go", ...}; «to miss (a flight)» → {"to miss", ...}."""
    base = re.sub(r"\(.*?\)", "", en).strip()
    forms = {en, base}
    if " – " in base:
        forms.add(base.split(" – ")[0])
    for f in list(forms):
        if f.startswith("to "):
            forms.add(f[3:])
    return {normalize(f) for f in forms if f}


@router.message(CheckVocab.answering, F.text)
async def on_vocab_answer(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    check = (await state.get_data()).get("check")
    if not check:
        await state.set_state(None)
        return
    word = await session.get(Word, check["word_ids"][check["vocab_idx"]])
    if normalize(message.text) in accepted_forms(word.en):
        check["vocab_correct"] += 1
        await message.answer("✅")
    else:
        check["vocab_wrong"].append(word.id)
        await message.answer(f"❌ {html.escape(word.en)}")
        # Слово, которое не вспомнил на проверке, отправляем на повторение прямо сейчас
        card = await session.scalar(select(UserWord).where(UserWord.user_id == user.id, UserWord.word_id == word.id))
        if card:
            card.interval_days, card.repetitions = 0, 0
            card.due_at = utcnow()
    check["vocab_idx"] += 1
    await state.update_data(check=check)
    if check["vocab_idx"] < len(check["word_ids"]):
        await ask_vocab(message, session, state)
    else:
        await state.set_state(None)
        await finish_check(message, session, user, state)


async def finish_check(message: Message, session: AsyncSession, user: User, state: FSMContext) -> None:
    check = (await state.get_data())["check"]
    await state.update_data(check=None)

    g_total, g_correct = len(check["grammar_keys"]), check["grammar_correct"]
    v_total, v_correct = len(check["word_ids"]), check["vocab_correct"]
    total, score = g_total + v_total, g_correct + v_correct

    # Разбивка по слабым местам из теста
    per_spot: dict[str, list[int]] = {}
    for key in check["grammar_keys"]:
        spot = LESSONS_BY_ID[lesson_id_of(get_question(key)[0])].weak_spot
        stat = per_spot.setdefault(spot, [0, 0])
        stat[1] += 1
        stat[0] += key not in check["grammar_wrong"]

    previous = await session.scalar(
        select(TestResult).where(TestResult.user_id == user.id, TestResult.kind == "weekly")
        .order_by(TestResult.created_at.desc()).limit(1))
    session.add(TestResult(user_id=user.id, kind="weekly", score=score, total=total,
                           details=json.dumps({"per_spot": per_spot, "vocab": [v_correct, v_total]})))
    await session.flush()

    pct = round(100 * score / total)
    lines = [f"🧪 <b>Результат: {score}/{total} ({pct}%)</b>\n{game.progress_bar(score, total, 20)}\n"]
    for spot, (ok, n) in per_spot.items():
        mark = "✅" if ok == n else ("🟡" if ok * 2 >= n else "🔴")
        lines.append(f"{mark} {WEAK_SPOT_NAMES[spot]}: {ok}/{n}")
    if v_total:
        lines.append(f"{'✅' if v_correct == v_total else '🟡'} Слова: {v_correct}/{v_total}")
    if previous:
        prev_pct = round(100 * previous.score / previous.total)
        diff = pct - prev_pct
        lines.append(f"\n{'📈' if diff >= 0 else '📉'} {'+' if diff >= 0 else ''}{diff}% к прошлой проверке")

    weakest = min(per_spot.items(), key=lambda kv: kv[1][0] / kv[1][1], default=None)
    if weakest and weakest[1][0] < weakest[1][1]:
        lines.append(f"\n👉 Подтяни: <b>{WEAK_SPOT_NAMES[weakest[0]]}</b>. Ошибки уже в «Работе над ошибками».")

    lines.append((await game.award(session, user, 20 + 3 * score, "check")).text())
    if score == total:
        if msg := await game.grant_achievement(session, user, "perfect_test"):
            lines.append(msg)
    await message.answer("\n".join(lines))
