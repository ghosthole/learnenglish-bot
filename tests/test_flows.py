"""Сквозные сценарии: пользователь нажимает кнопки, бот отвечает без ошибок."""
from sqlalchemy import func, select

from bot.db.models import GrammarProgress, User, UserQuest, UserWord
from bot.keyboards.menu import (BTN_CHECK, BTN_GRAMMAR, BTN_LISTENING, BTN_PROFILE, BTN_QUESTS,
                                BTN_SETTINGS, BTN_SPRINT, BTN_WORDS)


async def test_start_and_menu(harness):
    sent = await harness.text("/start")
    assert any("A2" in t for t in harness.texts(sent))
    for button in (BTN_WORDS, BTN_GRAMMAR, BTN_LISTENING, BTN_QUESTS, BTN_CHECK, BTN_PROFILE, BTN_SETTINGS):
        sent = await harness.text(button)
        assert sent, f"нет ответа на {button}"


async def test_new_words_and_review(harness):
    await harness.text("/start")
    sent = await harness.click("words:new")
    assert "Новые слова" in harness.texts(sent)[0]
    async with harness.sessionmaker() as s:
        assert await s.scalar(select(func.count()).select_from(UserWord)) == 7

    # Проходим повторение: на каждую карточку жмём «показать» → «помню» или первый вариант квиза
    sent = await harness.click("words:review")
    for _ in range(30):
        buttons = harness.buttons(sent)
        show = [d for t, d in buttons if d.startswith("w:show")]
        pick = [d for t, d in buttons if d.startswith("w:pick")]
        if show:
            sent = await harness.click(show[0])
            grade = [d for t, d in harness.buttons(sent) if d.startswith("w:grade") and d.endswith(":2")]
            sent = await harness.click(grade[0])
        elif pick:
            sent = await harness.click(pick[0])
        else:
            break
    assert any("Сессия закончена" in t for t in harness.texts(sent))
    async with harness.sessionmaker() as s:
        user = await s.get(User, 42)
        assert user.xp > 0 and user.streak == 1


async def test_add_custom_words(harness):
    await harness.text("/add")
    sent = await harness.text("cliffhanger - обрыв\nto binge-watch - смотреть запоем")
    assert "Добавил 2" in harness.texts(sent)[0]


async def test_grammar_lesson(harness):
    await harness.text("/grammar")
    await harness.click("g:open:present_simple:0")
    sent = await harness.click("g:practice:present_simple:0")
    for _ in range(20):
        answers = [d for t, d in harness.buttons(sent) if d.startswith("g:ans")]
        if answers:
            sent = await harness.click(answers[0])
        elif any("Напиши ответ" in t for t in harness.texts(sent)):
            sent = await harness.text("studies")
        else:
            break
    assert any("XP" in t for t in harness.texts(sent))
    async with harness.sessionmaker() as s:
        progress = await s.scalar(select(GrammarProgress))
        assert progress.attempts == 1


async def test_menu_button_exits_text_question(harness):
    """Нажатие кнопки меню во время письменного вопроса не считается ответом."""
    await harness.text("/grammar")
    sent = await harness.click("g:practice:conditional_3:0")
    for _ in range(10):
        if any("Напиши ответ" in t for t in harness.texts(sent)):
            break
        answers = [d for t, d in harness.buttons(sent) if d.startswith("g:ans")]
        sent = await harness.click(answers[0])
    sent = await harness.text(BTN_PROFILE)
    assert any("Уровень" in t for t in harness.texts(sent))


async def test_sprint(harness):
    await harness.text("/start")
    sent = await harness.click("sprint:start")
    for _ in range(60):
        buttons = harness.buttons(sent)
        data = [d for _, d in buttons]
        if any("5-минутка закрыта" in t for t in harness.texts(sent)):
            break
        if (d := next((d for d in data if d.startswith("w:show")), None)):
            sent = await harness.click(d)
            sent = await harness.click(next(d for _, d in harness.buttons(sent) if d.startswith("w:grade")))
        elif (d := next((d for d in data if d.startswith(("w:pick", "g:ans"))), None)):
            sent = await harness.click(d)
        elif "sprint:next" in data:
            sent = await harness.click("sprint:next")
        elif any("Напиши ответ" in t for t in harness.texts(sent)):
            sent = await harness.text("idk")
        else:
            raise AssertionError(f"5-минутка застряла: {harness.texts(sent)}")
    assert any("5-минутка закрыта" in t for t in harness.texts(sent))


async def test_quest_words_submission(harness):
    await harness.text(BTN_QUESTS)
    async with harness.sessionmaker() as s:
        uq = await s.scalar(select(UserQuest).limit(1))
        # Подменяем квест на «серию + 10 слов», чтобы проверить сдачу списком слов
        uq.quest_id = "series_10_words"
        await s.commit()
        uq_id = uq.id
    await harness.click(f"q:open:{uq_id}")
    sent = await harness.text("one - один\ntwo - два")
    assert "из 10" in harness.texts(sent)[0]
    words = "\n".join(f"word{i} - слово{i}" for i in range(10))
    sent = await harness.text(words)
    assert any("выполнен" in t for t in harness.texts(sent))
    async with harness.sessionmaker() as s:
        assert (await s.get(UserQuest, uq_id)).status == "done"


async def test_listening_story(harness):
    await harness.text(BTN_LISTENING)
    await harness.click("ls:story")
    sent = await harness.click("ls:quiz:rainy_day")
    for _ in range(5):
        answers = [d for _, d in harness.buttons(sent) if d.startswith("g:ans")]
        if not answers:
            break
        sent = await harness.click(answers[0])
    assert any("Понял" in t for t in harness.texts(sent))


async def test_weekly_check(harness):
    await harness.text("/start")
    await harness.click("words:new")
    async with harness.sessionmaker() as s:
        for card in await s.scalars(select(UserWord)):
            card.repetitions = 1
        await s.commit()
    sent = await harness.click("check:start")
    for _ in range(30):
        answers = [d for _, d in harness.buttons(sent) if d.startswith("g:ans")]
        texts = harness.texts(sent)
        if any("Результат" in t for t in texts):
            break
        if answers:
            sent = await harness.click(answers[0])
        else:
            sent = await harness.text("something")
    assert any("Результат" in t for t in harness.texts(sent))


async def test_settings(harness):
    await harness.text(BTN_SETTINGS)
    sent = await harness.click("s:menu:time")
    time_buttons = dict(harness.buttons(sent))
    await harness.click(time_buttons["08:30"])
    async with harness.sessionmaker() as s:
        assert (await s.get(User, 42)).reminder_time.strftime("%H:%M") == "08:30"
