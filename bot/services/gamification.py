"""Очки (XP), уровни, стрики, ачивки и лутбоксы.

Главная функция — `award()`: начисляет XP, обновляет стрик и возвращает
список коротких сообщений («+10 XP», «Новый уровень!», «Ачивка!»),
которые хендлер показывает пользователю.
"""
import math
import random
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Achievement, GrammarProgress, User, UserQuest, UserWord, XpEvent
from bot.services.timeutils import start_of_user_day_utc, user_now, user_today

LEVEL_TITLES = [
    "🥚 Яйцо", "🐣 Птенец", "🐥 Цыплёнок", "🦆 Утка с амбициями", "🦊 Хитрый лис",
    "🐺 Одинокий волк", "🦅 Орёл", "🐉 Дракон", "🦄 Единорог", "👑 B1 Legend",
]

ACHIEVEMENTS: dict[str, str] = {
    "first_steps": "👣 Первые шаги — заработал первые XP",
    "words_10": "🌱 10 слов в работе",
    "words_50": "🌿 50 слов в работе",
    "words_150": "🌳 150 слов в работе",
    "learned_25": "🧠 25 слов выучено намертво",
    "streak_3": "🔥 Стрик 3 дня",
    "streak_7": "🔥🔥 Стрик неделя",
    "streak_30": "☄️ Стрик 30 дней",
    "grammar_1": "📖 Первый урок грамматики",
    "grammar_5": "📚 5 уроков грамматики",
    "quest_1": "🎯 Первый квест",
    "quest_10": "🏹 10 квестов",
    "combo_10": "⚡ Комбо x10",
    "night_owl": "🦉 Сова — учился после 23:00",
    "early_bird": "🐦 Ранняя пташка — учился до 8:00",
    "perfect_test": "💯 Идеальная проверка",
    "level_5": "🦊 5 уровень",
}


def level_for_xp(xp: int) -> int:
    """Уровень L требует 50·(L−1)² XP: 2 ур. — 50, 3 — 200, 5 — 800, 10 — 4050."""
    return int(math.sqrt(max(xp, 0) / 50)) + 1


def xp_for_level(level: int) -> int:
    return 50 * (level - 1) ** 2


def level_title(level: int) -> str:
    return LEVEL_TITLES[min(level, len(LEVEL_TITLES)) - 1]


def progress_bar(value: int, total: int, width: int = 10) -> str:
    filled = 0 if total <= 0 else min(width, round(width * value / total))
    return "▰" * filled + "▱" * (width - filled)


@dataclass
class AwardResult:
    xp: int
    messages: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join(self.messages)


def update_streak(user: User) -> str | None:
    """Обновляет стрик при первой активности за день. Возвращает сообщение или None."""
    today = user_today(user)
    last = user.last_active_date
    if last == today:
        return None

    message = None
    if last is not None and (today - last).days == 1:
        user.streak += 1
        message = f"🔥 Стрик: {user.streak} дн. подряд!"
    elif last is not None and (today - last).days == 2 and user.streak_freezes > 0:
        user.streak_freezes -= 1
        user.streak += 1
        message = f"🧊 Заморозка спасла стрик! Стрик: {user.streak} дн."
    else:
        if user.streak > 1:
            message = f"💔 Стрик сгорел (было {user.streak}). Начинаем заново, ты сможешь!"
        user.streak = 1

    user.best_streak = max(user.best_streak, user.streak)
    user.last_active_date = today
    # Каждые 7 дней стрика — бонусная заморозка (максимум 3)
    if user.streak % 7 == 0 and user.streak_freezes < 3:
        user.streak_freezes += 1
        message = (message or "") + "\n🧊 +1 заморозка стрика за неделю без пропусков!"
    return message


async def daily_xp(session: AsyncSession, user: User) -> int:
    return await session.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0))
        .where(XpEvent.user_id == user.id, XpEvent.created_at >= start_of_user_day_utc(user))
    ) or 0


async def grant_achievement(session: AsyncSession, user: User, code: str) -> str | None:
    exists = await session.scalar(
        select(Achievement.id).where(Achievement.user_id == user.id, Achievement.code == code)
    )
    if exists:
        return None
    session.add(Achievement(user_id=user.id, code=code))
    await session.flush()
    return f"🏆 Ачивка: {ACHIEVEMENTS[code]}"


async def check_achievements(session: AsyncSession, user: User) -> list[str]:
    earned = set(await session.scalars(select(Achievement.code).where(Achievement.user_id == user.id)))
    candidates: list[str] = []

    def want(code: str, condition: bool) -> None:
        if condition and code not in earned:
            candidates.append(code)

    want("first_steps", user.xp > 0)
    want("streak_3", user.streak >= 3)
    want("streak_7", user.streak >= 7)
    want("streak_30", user.streak >= 30)
    want("level_5", level_for_xp(user.xp) >= 5)

    hour = user_now(user).hour
    want("night_owl", hour >= 23)
    want("early_bird", 5 <= hour < 8)

    words = await session.scalar(
        select(func.count()).select_from(UserWord).where(UserWord.user_id == user.id)) or 0
    want("words_10", words >= 10)
    want("words_50", words >= 50)
    want("words_150", words >= 150)
    learned = await session.scalar(
        select(func.count()).select_from(UserWord)
        .where(UserWord.user_id == user.id, UserWord.interval_days >= 21)) or 0
    want("learned_25", learned >= 25)

    lessons = await session.scalar(
        select(func.count()).select_from(GrammarProgress)
        .where(GrammarProgress.user_id == user.id, GrammarProgress.completed_at.is_not(None))) or 0
    want("grammar_1", lessons >= 1)
    want("grammar_5", lessons >= 5)

    quests = await session.scalar(
        select(func.count()).select_from(UserQuest)
        .where(UserQuest.user_id == user.id, UserQuest.status == "done")) or 0
    want("quest_1", quests >= 1)
    want("quest_10", quests >= 10)

    messages = []
    for code in candidates:
        msg = await grant_achievement(session, user, code)
        if msg:
            messages.append(msg)
    return messages


async def award(session: AsyncSession, user: User, amount: int, reason: str) -> AwardResult:
    """Начислить XP. Обновляет стрик, уровень, дневную цель и ачивки."""
    result = AwardResult(xp=amount)
    if amount <= 0:
        return result

    streak_msg = update_streak(user)
    before_daily = await daily_xp(session, user)
    old_level = level_for_xp(user.xp)

    user.xp += amount
    session.add(XpEvent(user_id=user.id, amount=amount, reason=reason))
    await session.flush()

    result.messages.append(f"<b>+{amount} XP</b>")
    if streak_msg:
        result.messages.append(streak_msg)

    new_level = level_for_xp(user.xp)
    if new_level > old_level:
        result.messages.append(f"🆙 <b>Новый уровень {new_level}!</b> Теперь ты {level_title(new_level)}")

    goal = user.daily_goal_xp
    if before_daily < goal <= before_daily + amount:
        result.messages.append("✅ <b>Дневная цель выполнена!</b> Красавчик 😎")

    result.messages.extend(await check_achievements(session, user))
    return result


async def maybe_lootbox(session: AsyncSession, user: User, chance: float = 0.2) -> str | None:
    """Случайный бонус после завершения сессии — маленький дофаминовый сюрприз."""
    if random.random() > chance:
        return None
    roll = random.random()
    if roll < 0.15 and user.streak_freezes < 3:
        user.streak_freezes += 1
        return "🎁 <b>Лутбокс!</b> Внутри: 🧊 заморозка стрика"
    bonus = random.choice([5, 10, 10, 15, 20, 30])
    res = await award(session, user, bonus, "lootbox")
    return "🎁 <b>Лутбокс!</b> Внутри: " + res.text()


def combo_message(combo: int) -> str | None:
    if combo in (3, 5) or (combo >= 10 and combo % 5 == 0):
        fire = "🔥" * min(combo // 3 + 1, 5)
        return f"{fire} Комбо x{combo}!"
    return None
