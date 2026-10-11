"""Профиль, статистика и настройки."""
from datetime import time, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.content.grammar import LESSONS
from bot.db.models import Achievement, GrammarProgress, User, UserQuest, XpEvent
from bot.keyboards.menu import BTN_PROFILE, BTN_SETTINGS
from bot.services import gamification as game
from bot.services import words as words_service
from bot.services.progress import b1_progress
from bot.services.timeutils import start_of_user_day_utc, start_of_user_week_utc, user_today

router = Router()


@router.message(F.text == BTN_PROFILE)
@router.message(Command("profile"))
async def profile(message: Message, session: AsyncSession, user: User) -> None:
    level = game.level_for_xp(user.xp)
    cur, nxt = game.xp_for_level(level), game.xp_for_level(level + 1)
    today = await game.daily_xp(session, user)
    week = await session.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0))
        .where(XpEvent.user_id == user.id, XpEvent.created_at >= start_of_user_week_utc(user))) or 0
    stats = await words_service.word_stats(session, user)
    passed = await session.scalar(
        select(func.count()).select_from(GrammarProgress)
        .where(GrammarProgress.user_id == user.id, GrammarProgress.best_score >= 70)) or 0
    quests = await session.scalar(
        select(func.count()).select_from(UserQuest)
        .where(UserQuest.user_id == user.id, UserQuest.status == "done")) or 0
    achievements = await session.scalar(
        select(func.count()).select_from(Achievement).where(Achievement.user_id == user.id)) or 0
    b1 = await b1_progress(session, user)

    text = (
        f"👤 <b>{user.first_name or 'Ты'}</b> · {game.level_title(level)}\n\n"
        f"⭐ Уровень <b>{level}</b> · {user.xp} XP\n"
        f"{game.progress_bar(user.xp - cur, nxt - cur)} до {level + 1} ур.: {nxt - user.xp} XP\n\n"
        f"🎯 Сегодня: {today}/{user.daily_goal_xp} XP {game.progress_bar(today, user.daily_goal_xp)}\n"
        f"📅 За неделю: {week} XP\n"
        f"🔥 Стрик: <b>{user.streak}</b> дн. (рекорд {user.best_streak}) · 🧊 заморозок: {user.streak_freezes}\n\n"
        f"📚 Слов: {stats['total']} (выучено {stats['learned']})\n"
        f"📖 Грамматика: {passed}/{len(LESSONS)} уроков\n"
        f"🎯 Квестов выполнено: {quests}\n"
        f"🏆 Ачивок: {achievements}/{len(game.ACHIEVEMENTS)}\n\n"
        f"🗺 <b>Путь к B1: {b1}%</b>\n{game.progress_bar(b1, 100, width=20)}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🏆 Ачивки", callback_data="profile:ach")
    kb.button(text="📈 Неделя", callback_data="profile:week")
    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "profile:ach")
async def cb_achievements(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    await callback.answer()
    earned = set(await session.scalars(select(Achievement.code).where(Achievement.user_id == user.id)))
    lines = ["🏆 <b>Ачивки</b>\n"]
    for code, title in game.ACHIEVEMENTS.items():
        lines.append(("✅ " if code in earned else "🔒 ") + title)
    await callback.message.answer("\n".join(lines))


@router.callback_query(F.data == "profile:week")
async def cb_week(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    await callback.answer()
    today = user_today(user)
    lines = ["📈 <b>XP за 7 дней</b>\n"]
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    values = []
    for day in days:
        start, end = start_of_user_day_utc(user, day), start_of_user_day_utc(user, day + timedelta(days=1))
        values.append(await session.scalar(
            select(func.coalesce(func.sum(XpEvent.amount), 0))
            .where(XpEvent.user_id == user.id, XpEvent.created_at >= start, XpEvent.created_at < end)) or 0)
    top = max(values + [user.daily_goal_xp])
    names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day, value in zip(days, values):
        mark = "✅" if value >= user.daily_goal_xp else ("▫️" if value == 0 else "🟡")
        lines.append(f"<code>{names[day.weekday()]} {game.progress_bar(value, top, 12)}</code> {value} {mark}")
    await callback.message.answer("\n".join(lines))


# ---------- Настройки ----------

class SetCb(CallbackData, prefix="s"):
    action: str  # time | tz | goal | words | toggle | menu
    value: str = ""


TIMEZONES = {
    "Europe/Kaliningrad": "Калининград (МСК−1)",
    "Europe/Moscow": "Москва (МСК)",
    "Europe/Samara": "Самара (МСК+1)",
    "Asia/Yekaterinburg": "Екатеринбург (МСК+2)",
    "Asia/Omsk": "Омск (МСК+3)",
    "Asia/Novosibirsk": "Новосибирск (МСК+4)",
    "Asia/Irkutsk": "Иркутск (МСК+5)",
    "Asia/Vladivostok": "Владивосток (МСК+7)",
}


def settings_text(user: User) -> str:
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"⏰ Напоминание: <b>{user.reminder_time.strftime('%H:%M')}</b> "
        f"({'вкл' if user.reminders_enabled else 'выкл'})\n"
        f"🌍 Часовой пояс: <b>{TIMEZONES.get(user.timezone, user.timezone)}</b>\n"
        f"🎯 Дневная цель: <b>{user.daily_goal_xp} XP</b>\n"
        f"✨ Новых слов в день: <b>{user.new_words_per_day}</b>"
    )


def settings_kb(user: User):
    kb = InlineKeyboardBuilder()
    kb.button(text="⏰ Время напоминания", callback_data=SetCb(action="menu", value="time"))
    kb.button(text="🔔 Выключить" if user.reminders_enabled else "🔔 Включить",
              callback_data=SetCb(action="toggle"))
    kb.button(text="🌍 Часовой пояс", callback_data=SetCb(action="menu", value="tz"))
    kb.button(text="🎯 Цель на день", callback_data=SetCb(action="menu", value="goal"))
    kb.button(text="✨ Слов в день", callback_data=SetCb(action="menu", value="words"))
    kb.adjust(2, 1, 2)
    return kb.as_markup()


@router.message(F.text == BTN_SETTINGS)
@router.message(Command("settings"))
async def settings(message: Message, user: User) -> None:
    await message.answer(settings_text(user), reply_markup=settings_kb(user))


@router.callback_query(SetCb.filter(F.action == "menu"))
async def cb_settings_menu(callback: CallbackQuery, callback_data: SetCb, user: User) -> None:
    await callback.answer()
    kb = InlineKeyboardBuilder()
    if callback_data.value == "time":
        for hour in range(7, 24):
            for minute in (0, 30):
                kb.button(text=f"{hour:02d}:{minute:02d}", callback_data=SetCb(action="time", value=f"{hour}:{minute}"))
        kb.adjust(4)
        title = "⏰ Во сколько напоминать?"
    elif callback_data.value == "tz":
        for tz, name in TIMEZONES.items():
            kb.button(text=name, callback_data=SetCb(action="tz", value=tz))
        kb.adjust(1)
        title = "🌍 Твой часовой пояс:"
    elif callback_data.value == "goal":
        for goal in (30, 50, 80, 120):
            kb.button(text=f"{goal} XP", callback_data=SetCb(action="goal", value=str(goal)))
        kb.adjust(4)
        title = "🎯 Сколько XP в день? (5-минутка ≈ 30–40 XP)"
    else:
        for n in (3, 5, 7, 10, 15):
            kb.button(text=str(n), callback_data=SetCb(action="words", value=str(n)))
        kb.adjust(5)
        title = "✨ Сколько новых слов в день? Рекомендую 5–10."
    await callback.message.edit_text(title, reply_markup=kb.as_markup())


@router.callback_query(SetCb.filter(F.action.in_({"time", "tz", "goal", "words", "toggle"})))
async def cb_settings_set(callback: CallbackQuery, callback_data: SetCb, user: User) -> None:
    action, value = callback_data.action, callback_data.value
    if action == "time":
        hour, minute = map(int, value.split(":"))
        user.reminder_time = time(hour, minute)
        user.reminders_enabled = True
    elif action == "tz" and value in TIMEZONES:
        user.timezone = value
    elif action == "goal":
        user.daily_goal_xp = int(value)
    elif action == "words":
        user.new_words_per_day = int(value)
    elif action == "toggle":
        user.reminders_enabled = not user.reminders_enabled
    await callback.answer("Сохранено ✅")
    await callback.message.edit_text(settings_text(user), reply_markup=settings_kb(user))
