"""Напоминания. Планировщик раз в минуту проверяет, кому пора написать.

- Ежедневное напоминание в выбранное время (если дневная цель ещё не выполнена).
- «Спасение стрика» вечером, если сегодня ещё не занимался.
- По воскресеньям — напоминание про еженедельную проверку.
"""
import logging
import random
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.content.fun import BRAIN_BREAKS, REMINDERS, STREAK_WARNINGS
from bot.db.models import User
from bot.services import gamification as game
from bot.services import words as words_service
from bot.services.timeutils import user_now

log = logging.getLogger(__name__)

REMINDER_WINDOW = timedelta(hours=2)  # если бот был выключен, не шлём «утреннее» напоминание вечером
STREAK_WARNING_HOUR = 21


def sprint_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ 5-минутка", callback_data="sprint:start")
    kb.button(text="🔁 Слова", callback_data="words:review")
    kb.adjust(2)
    return kb.as_markup()


async def process_user(bot: Bot, session: AsyncSession, user: User) -> None:
    local = user_now(user)
    today = local.date()
    name = user.first_name or "бро"

    reminder_at = datetime.combine(today, user.reminder_time, tzinfo=local.tzinfo)
    if user.last_reminded_on != today and reminder_at <= local < reminder_at + REMINDER_WINDOW:
        user.last_reminded_on = today
        if await game.daily_xp(session, user) < user.daily_goal_xp:
            due = await words_service.count_due(session, user)
            text = random.choice(REMINDERS).format(name=name, due=due, streak=user.streak)
            if local.weekday() == 6:
                text += "\n\n🧪 Сегодня воскресенье — день недельной проверки! /check"
            text += "\n\n" + random.choice(BRAIN_BREAKS)
            await bot.send_message(user.id, text, reply_markup=sprint_kb())

    if (local.hour >= STREAK_WARNING_HOUR and user.streak > 0 and user.last_active_date != today
            and user.last_streak_warning_on != today):
        user.last_streak_warning_on = today
        text = random.choice(STREAK_WARNINGS).format(name=name, streak=user.streak)
        await bot.send_message(user.id, text, reply_markup=sprint_kb())


async def tick(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        users = list(await session.scalars(select(User).where(User.reminders_enabled.is_(True))))
        for user in users:
            try:
                await process_user(bot, session, user)
            except TelegramForbiddenError:
                log.info("Пользователь %s заблокировал бота, выключаю напоминания", user.id)
                user.reminders_enabled = False
            except Exception:
                log.exception("Ошибка напоминания для %s", user.id)
        await session.commit()


def setup_scheduler(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(tick, "interval", minutes=1, args=[bot, sessionmaker],
                      id="reminders", max_instances=1, coalesce=True)
    return scheduler
