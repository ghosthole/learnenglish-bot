"""Работа со временем пользователя."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from bot.db.models import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def user_now(user: User) -> datetime:
    return utcnow().astimezone(user_tz(user))


def user_today(user: User) -> date:
    return user_now(user).date()


def start_of_user_day_utc(user: User, day: date | None = None) -> datetime:
    """Начало дня пользователя (полночь по его часовому поясу) в UTC."""
    day = day or user_today(user)
    local_midnight = datetime.combine(day, time.min, tzinfo=user_tz(user))
    return local_midnight.astimezone(timezone.utc)


def start_of_user_week_utc(user: User) -> datetime:
    today = user_today(user)
    return start_of_user_day_utc(user, today - timedelta(days=today.weekday()))
