from datetime import date, datetime, time, timedelta, timezone

from bot.content.grammar import LESSONS
from bot.content.listening import STORIES
from bot.content.quests import QUESTS
from bot.content.words import ALL_WORDS
from bot.db.models import User
from bot.handlers.check import accepted_forms
from bot.services import gamification as game
from bot.services import srs
from bot.services.checker import check_static, normalize
from bot.services.timeutils import user_today
from bot.services.words import parse_word_lines

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def test_srs_intervals_grow():
    state = srs.CardState()
    intervals = []
    for _ in range(4):
        state, due = srs.review(state, srs.Grade.GOOD, NOW)
        intervals.append(state.interval_days)
    assert intervals[:2] == [1, 3]
    assert intervals[2] > intervals[1] and intervals[3] > intervals[2]


def test_srs_again_resets():
    state = srs.CardState(interval_days=10, repetitions=4)
    state, due = srs.review(state, srs.Grade.AGAIN, NOW)
    assert state.repetitions == 0 and state.lapses == 1
    assert due - NOW == timedelta(minutes=10)
    assert state.ease >= srs.MIN_EASE


def test_parse_word_lines():
    pairs = parse_word_lines("1. to binge-watch - смотреть запоем\n2) cliffhanger — обрыв\nмусор")
    assert pairs == [("to binge-watch", "смотреть запоем"), ("cliffhanger", "обрыв")]


def test_normalize_contractions():
    assert normalize("She doesn’t watch TV!") == normalize("she does not watch tv")
    assert check_static("I'm watching a series now.", ["i am watching a series now"])


def test_accepted_forms():
    assert "book" in accepted_forms("to book")
    assert "go" in accepted_forms("go – went – gone")


def test_levels():
    assert game.level_for_xp(0) == 1
    assert game.level_for_xp(50) == 2
    assert game.level_for_xp(199) == 2
    assert game.level_for_xp(200) == 3


def make_user(**kw) -> User:
    defaults = dict(id=1, timezone="Europe/Moscow", streak=0, best_streak=0, streak_freezes=1,
                    last_active_date=None, reminder_time=time(19))
    defaults.update(kw)
    return User(**defaults)


def test_streak_continues_and_freezes():
    user = make_user()
    game.update_streak(user)
    assert user.streak == 1

    today = user_today(user)
    user.last_active_date = today - timedelta(days=1)
    game.update_streak(user)
    assert user.streak == 2

    user.last_active_date = today - timedelta(days=2)
    msg = game.update_streak(user)
    assert user.streak == 3 and user.streak_freezes == 0 and "Заморозка" in msg

    user.last_active_date = today - timedelta(days=3)
    game.update_streak(user)
    assert user.streak == 1 and user.best_streak == 3


def test_content_integrity():
    assert len({w[0] for w in ALL_WORDS}) == len(ALL_WORDS), "дубли в словаре"
    assert len({lesson.id for lesson in LESSONS}) == len(LESSONS)
    for lesson in LESSONS + STORIES:
        for q in lesson.questions:
            if q.kind == "choice":
                assert 0 <= q.answer < len(q.options), q.prompt
            else:
                assert q.answers, q.prompt
    assert len({q.id for q in QUESTS}) == len(QUESTS)
    assert {q.size for q in QUESTS} == {"small", "medium", "big"}
    # callback_data в Telegram ограничена 64 байтами
    for lesson in LESSONS:
        assert len(f"g:practice:{lesson.id}:0".encode()) <= 64
