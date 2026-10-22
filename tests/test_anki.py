"""Импорт из Anki: разбор .apkg (старый и новый формат), .txt и запись в базу."""
import io
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import zstandard
from sqlalchemy import select

from bot.db.models import User, UserWord, Word
from bot.services import anki

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
CRT = int((NOW - timedelta(days=100)).timestamp())

YOMITAN = ('<div class="yomitan-glossary"><ol><li data-dictionary="wty-en-ru"><i>(v, wty-en-ru)</i> '
           '<span><ol data-sc-content="glosses"><li><div>избегать, сторониться<details><summary>1 пример</summary>'
           '<div>Avoid the city centre.</div></details></div></li><li><div>устар. аннулировать</div></li>'
           '</ol><div data-sc-content="backlink"><a href="x">Wiktionary</a></div></span></li>'
           '<style>.x { color: red; }</style></ol></div>')


def make_apkg(new_format: bool) -> bytes:
    """Мини-колода: тип записи Word/Definition/Sentence и три записи."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "c.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE col (crt INTEGER, models TEXT)")
        conn.execute("CREATE TABLE notes (id INTEGER, mid INTEGER, flds TEXT)")
        conn.execute("CREATE TABLE cards (nid INTEGER, type INTEGER, queue INTEGER, due INTEGER, ivl INTEGER,"
                     " factor INTEGER, reps INTEGER, lapses INTEGER)")
        names = ["Word", "Definition", "Sentence"]
        if new_format:
            conn.execute("CREATE TABLE fields (ntid INTEGER, name TEXT, ord INTEGER)")
            conn.executemany("INSERT INTO fields VALUES (1, ?, ?)", [(n, i) for i, n in enumerate(names)])
            conn.execute("INSERT INTO col VALUES (?, '')", (CRT,))
        else:
            models = {"1": {"flds": [{"name": n, "ord": i} for i, n in enumerate(names)]}}
            conn.execute("INSERT INTO col VALUES (?, ?)", (CRT, json.dumps(models)))
        notes = [
            (10, ["avoid", YOMITAN, "1) Привет 2) I try to avoid sugar. [sound:a.wav]"]),
            (11, ["knee", "колено", ""]),
            (12, ["countryside", "", ""]),  # без перевода
        ]
        conn.executemany("INSERT INTO notes VALUES (?, 1, ?)", [(i, "\x1f".join(f)) for i, f in notes])
        conn.executemany("INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            (10, 2, 2, 130, 30, 2300, 9, 1),  # на повторении, следующий показ через 30 дней
            (11, 0, 0, 1, 0, 0, 0, 0),        # новая
        ])
        conn.commit()
        conn.close()
        raw = path.read_bytes()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if new_format:
            zf.writestr("collection.anki21b", zstandard.ZstdCompressor().compress(raw))
            zf.writestr("collection.anki2", b"dummy")
        else:
            zf.writestr("collection.anki2", raw)
        zf.writestr("media", "{}")
    return buf.getvalue()


def test_parse_apkg_both_formats():
    for new_format in (True, False):
        notes = {n.en: n for n in anki.parse_package(make_apkg(new_format), now=NOW)}
        assert set(notes) == {"avoid", "knee", "countryside"}
        avoid = notes["avoid"]
        assert avoid.ru == "избегать, сторониться"
        assert avoid.example == "I try to avoid sugar."
        assert avoid.schedule.interval_days == 30
        assert avoid.schedule.due_at.date() == (NOW + timedelta(days=30)).date()
        assert notes["knee"].schedule is None
        assert notes["countryside"].ru == ""


def test_parse_text_export():
    data = ("#separator:tab\n#html:true\n"
            "consider\tрассматривать<br>обдумывать\n"
            "колено\tknee\n"  # обратная карточка
            "\n").encode()
    notes = anki.parse_anki_file(data, "deck.txt")
    assert [(n.en, n.ru) for n in notes] == [("consider", "рассматривать; обдумывать"), ("knee", "колено")]


async def test_import_notes(harness):
    await harness.text("/start")
    notes = anki.parse_package(make_apkg(True), now=NOW)
    async with harness.sessionmaker() as s:
        user = await s.get(User, 42)
        report = await anki.import_notes(s, user, notes, now=NOW)
        assert (report.added, report.with_progress, report.skipped) == (2, 1, ["countryside"])
        again = await anki.import_notes(s, user, notes, now=NOW)
        assert again.added == 0 and again.already == 2
        await s.commit()

        cards = {c.word.en: c for c in await s.scalars(select(UserWord).join(Word).where(Word.topic == "anki"))}
        assert cards["avoid"].interval_days == 30
        assert cards["knee"].interval_days == 0


async def test_import_via_telegram(harness, monkeypatch):
    """Пользователь присылает .apkg документом — бот добавляет слова."""
    from aiogram.types import Document

    data = make_apkg(True)

    async def fake_download(self, file, destination=None, **kwargs):
        destination.write(data)
        return destination

    monkeypatch.setattr("aiogram.Bot.download", fake_download)
    await harness.text("/start")
    doc = Document(file_id="f", file_unique_id="u", file_name="deck.apkg", file_size=len(data))
    sent = await harness.text(None, document=doc)
    assert any("добавил <b>2</b>" in t for t in harness.texts(sent))
