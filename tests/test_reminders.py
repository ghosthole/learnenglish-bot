from datetime import timedelta

from bot.db.models import User
from bot.services import reminders
from bot.services.timeutils import user_now


async def test_reminder_sent_once(harness):
    async with harness.sessionmaker() as s:
        user = User(id=42, first_name="Vlad", timezone="Europe/Moscow")
        s.add(user)
        await s.flush()
        now = user_now(user)
        user.reminder_time = (now - timedelta(minutes=1)).time().replace(second=0, microsecond=0)
        if user.reminder_time > now.time():  # переход через полночь — пропускаем тест
            return
        await s.commit()

    await reminders.tick(harness.bot, harness.sessionmaker)
    await reminders.tick(harness.bot, harness.sessionmaker)
    sent = [m for m in harness.fake.sent if type(m).__name__ == "SendMessage"]
    async with harness.sessionmaker() as s:
        assert (await s.get(User, 42)).last_reminded_on == user_now(user).date()
    daily = [m for m in sent if "сгорит" not in m.text and "SOS" not in m.text and "спасти" not in m.text]
    assert len(daily) == 1
