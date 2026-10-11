"""Таблицы базы данных.

Все даты и время хранятся в UTC. Перевод в часовой пояс пользователя
делается только при показе и при планировании напоминаний.
"""
from datetime import date, datetime, time, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Настройки
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    reminder_time: Mapped[time] = mapped_column(Time, default=time(19, 0))
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_goal_xp: Mapped[int] = mapped_column(Integer, default=50)
    new_words_per_day: Mapped[int] = mapped_column(Integer, default=7)

    # Геймификация
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date)
    streak_freezes: Mapped[int] = mapped_column(Integer, default=1)

    words: Mapped[list["UserWord"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Word(Base):
    """Слово из встроенного словаря или добавленное пользователем."""

    __tablename__ = "words"
    __table_args__ = (UniqueConstraint("en", "owner_id", name="uq_word_en_owner"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    en: Mapped[str] = mapped_column(String(128))
    ru: Mapped[str] = mapped_column(String(256))
    example: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(4), default="A2")
    # None — слово из общего словаря; иначе id пользователя, который его добавил
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class UserWord(Base):
    """Карточка слова в интервальном повторении (алгоритм SM-2)."""

    __tablename__ = "user_words"
    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_user_word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))

    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="words")
    word: Mapped[Word] = relationship(lazy="joined")


class GrammarProgress(Base):
    __tablename__ = "grammar_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_grammar_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(String(64))
    best_score: Mapped[int] = mapped_column(Integer, default=0)  # процент 0..100
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Mistake(Base):
    """Ошибка в грамматическом упражнении. Используется в режиме «Работа над ошибками»."""

    __tablename__ = "mistakes"
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_mistake"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_key: Mapped[str] = mapped_column(String(128))  # например "present_simple:3"
    topic: Mapped[str] = mapped_column(String(64))
    times_wrong: Mapped[int] = mapped_column(Integer, default=1)
    fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserQuest(Base):
    """Квест (задание за очки), выданный пользователю."""

    __tablename__ = "user_quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quest_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | done | skipped
    assigned_on: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission: Mapped[str | None] = mapped_column(Text)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)


class XpEvent(Base):
    """История начисления очков: из неё считаются дневной прогресс и статистика."""

    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_achievement"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestResult(Base):
    """Результат проверки знаний (еженедельный тест, контрольная по грамматике)."""

    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    score: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
