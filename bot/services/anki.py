"""Импорт слов из Anki.

Поддерживаются:
  .apkg / .colpkg — экспорт колоды или коллекции (Файл → Экспорт). Внутри zip
      с базой SQLite: collection.anki21b (новые версии Anki, сжата zstd),
      collection.anki21 или collection.anki2 (старые версии);
  .txt / .tsv — «Notes in Plain Text»: поля через табуляцию.

Из .apkg переносится и прогресс повторения: интервал, лёгкость, ошибки и дата
следующего показа, чтобы выученные в Anki слова не свалились все разом.
"""
import html
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User, UserWord
from bot.services.timeutils import utcnow

# Названия полей (в нижнем регистре), по которым понимаем, где слово, перевод и пример
WORD_FIELDS = ("word", "front", "expression", "english", "term", "vocab", "vocabulary", "слово", "лицевая сторона")
MEANING_FIELDS = ("definition", "back", "meaning", "translation", "glossary", "russian",
                  "перевод", "значение", "оборотная сторона")
EXAMPLE_FIELDS = ("sentence", "example", "examples", "context", "пример", "предложение")

MAX_MEANINGS = 3
MAX_RU_LEN = 70  # длинные определения обрезаем: перевод должен влезать в карточку и кнопку квиза
MAX_EXAMPLE_LEN = 200


@dataclass
class AnkiSchedule:
    interval_days: int
    ease: float
    repetitions: int
    lapses: int
    due_at: datetime | None  # None — карточка в Anki ещё новая


@dataclass
class AnkiNote:
    en: str
    ru: str
    example: str | None = None
    schedule: AnkiSchedule | None = None


class AnkiImportError(Exception):
    pass


# ---------- Очистка HTML ----------

_CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)
_DROP_BLOCKS = [
    re.compile(r"<style.*?</style>", re.S | re.I),
    re.compile(r"<script.*?</script>", re.S | re.I),
    re.compile(r"<details.*?</details>", re.S | re.I),  # примеры и этимология в словарях Yomitan
    re.compile(r"<div[^>]*data-sc-content=\"backlink\".*?</div>", re.S),
    re.compile(r"<span[^>]*data-sc-content=\"tag\".*?</span>", re.S),
    re.compile(r"<i>\([^<]*\)</i>", re.S),  # пометки вида (n, wty-en-ru)
    re.compile(r"\[sound:[^\]]*\]"),
    re.compile(r"<img[^>]*>", re.I),
]
# Словарные пометки в начале значения: «анат. колено», «разг. хреновый»
_LABEL_RE = re.compile(r"^\s*(?:(?:анат|биол|воен|груб|жарг|книжн|лингв|амер|брит|преим|разг|религ|сравн|"
                       r"юр|перен|спорт|тех|мед|хим|физ|муз|полит|экон|комп)\.\s*)+")
_OBSOLETE_RE = re.compile(r"^(?:устар|арх)\.")
_GLOSSES_RE = re.compile(r"<ol[^>]*data-sc-content=\"glosses\"[^>]*>(.*?)</ol>", re.S)


def strip_html(text: str, sep: str = " ") -> str:
    text = re.sub(r"<br\s*/?>|</div>|</li>|</p>", sep, text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ;,")


def clean_meaning(raw: str) -> str:
    """Достаёт перевод из поля: и простой текст, и разметку словарей Yomitan."""
    for pattern in _DROP_BLOCKS:
        raw = pattern.sub("", raw)
    blocks = _GLOSSES_RE.findall(raw)
    items = [strip_html(i) for b in blocks for i in re.split(r"<li[^>]*>", b)] if blocks else [strip_html(raw, "; ")]
    # Значения часто повторяются в разных словарных статьях — оставляем первые уникальные
    meanings: list[str] = []
    for item in items:
        for part in item.split(";"):
            if _OBSOLETE_RE.match(part.strip()):
                continue  # устаревшие значения только сбивают
            part = _LABEL_RE.sub("", part).strip(" ,")
            if part and part not in meanings:
                meanings.append(part)
    text = "; ".join(meanings[:MAX_MEANINGS])
    if len(text) > MAX_RU_LEN:
        text = text[:MAX_RU_LEN].rsplit(" ", 1)[0].rstrip(",;") + "…"
    return text


def pick_example(raw: str, word: str) -> str | None:
    """Из поля с примерами берём одно предложение, где встречается слово."""
    text = strip_html(raw)
    if not text:
        return None
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\s*\d+\)\s*", text) if s.strip()]
    stem = word.lower()[: max(4, len(word) - 2)]
    # Берём английское предложение со словом; мусор (смесь с русским, куски сайтов) пропускаем
    for sentence in sentences:
        if (stem in sentence.lower() and not _CYRILLIC_RE.search(sentence)
                and " " in sentence and len(sentence) <= MAX_EXAMPLE_LEN):
            return sentence
    return None


# ---------- Разбор файлов ----------

def _field_index(names: list[str], wanted: tuple[str, ...], default: int | None) -> int | None:
    lowered = [n.strip().lower() for n in names]
    for w in wanted:
        if w in lowered:
            return lowered.index(w)
    return default


def note_from_fields(fields: list[str], names: list[str] | None = None) -> AnkiNote | None:
    names = names or []
    wi = _field_index(names, WORD_FIELDS, 0)
    mi = _field_index(names, MEANING_FIELDS, 1 if len(fields) > 1 else None)
    ei = _field_index(names, EXAMPLE_FIELDS, None)
    if mi is None or mi >= len(fields) or wi >= len(fields):
        return None
    en, ru = strip_html(fields[wi]), clean_meaning(fields[mi])
    # Карточка могла быть «русский → английский» — переворачиваем
    if _CYRILLIC_RE.search(en) and not _CYRILLIC_RE.search(ru):
        en, ru = strip_html(fields[mi]), clean_meaning(fields[wi])
    if not en or len(en) > 128:
        return None
    # Слово без перевода тоже возвращаем (ru=""), чтобы сказать о нём при импорте
    example = pick_example(fields[ei], en) if ei is not None and ei < len(fields) else None
    return AnkiNote(en=en, ru=ru, example=example)


def parse_text(data: bytes) -> list[AnkiNote]:
    text = data.decode("utf-8-sig", errors="replace")
    separator = "\t"
    notes = []
    for line in text.splitlines():
        if line.startswith("#"):
            # Заголовки экспорта Anki: #separator:tab, #html:true, ...
            if line.lower().startswith("#separator:"):
                value = line.split(":", 1)[1].strip().lower()
                separator = {"tab": "\t", "comma": ",", "semicolon": ";", "pipe": "|", "space": " "}.get(value, value)
            continue
        if not line.strip():
            continue
        parts = line.split(separator)
        if len(parts) < 2:
            continue
        if note := note_from_fields(parts):
            notes.append(note)
    return notes


def _open_collection(zf: zipfile.ZipFile, tmpdir: str) -> sqlite3.Connection:
    names = set(zf.namelist())
    path = Path(tmpdir) / "collection.db"
    if "collection.anki21b" in names:
        import zstandard  # нужен только для новых .apkg

        raw = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(zf.read("collection.anki21b"))).read()
    elif "collection.anki21" in names:
        raw = zf.read("collection.anki21")
    elif "collection.anki2" in names:
        raw = zf.read("collection.anki2")
    else:
        raise AnkiImportError("В архиве нет коллекции Anki")
    path.write_bytes(raw)
    return sqlite3.connect(path)


def _field_names(conn: sqlite3.Connection) -> dict[int, list[str]]:
    """Названия полей для каждого типа записи (в новых версиях — таблица fields, в старых — JSON в col)."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    result: dict[int, list[str]] = {}
    if "fields" in tables:
        for ntid, name, _ in conn.execute("SELECT ntid, name, ord FROM fields ORDER BY ntid, ord"):
            result.setdefault(ntid, []).append(name)
    else:
        models = json.loads(conn.execute("SELECT models FROM col").fetchone()[0] or "{}")
        for mid, model in models.items():
            result[int(mid)] = [f["name"] for f in sorted(model["flds"], key=lambda f: f["ord"])]
    return result


def _schedule(card: tuple, crt: int, now: datetime) -> AnkiSchedule | None:
    ctype, queue, due, ivl, factor, reps, lapses = card
    if ctype == 0 or queue < 0:  # новая или приостановленная карточка
        return None
    ease = min(3.5, max(1.3, factor / 1000)) if factor else 2.5
    if ctype == 2 and queue == 2:  # на повторении: due — номер дня от создания коллекции
        due_at = datetime.fromtimestamp(crt, timezone.utc) + timedelta(days=due)
    else:  # в процессе изучения: показать сразу
        due_at = now
    # repetitions в SM-2 — сколько раз подряд вспомнил; по интервалу это примерно:
    repetitions = 0 if ivl <= 0 else (1 if ivl < 3 else 2 + int(ivl >= 21))
    return AnkiSchedule(interval_days=max(0, ivl), ease=ease, repetitions=repetitions,
                        lapses=lapses, due_at=due_at)


def parse_package(data: bytes, now: datetime | None = None) -> list[AnkiNote]:
    now = now or datetime.now(timezone.utc)
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise AnkiImportError("Файл не похож на экспорт Anki (.apkg)") from e
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = _open_collection(zf, tmpdir)
        try:
            names = _field_names(conn)
            crt = conn.execute("SELECT crt FROM col").fetchone()[0]
            # По одной (самой «продвинутой») карточке на запись
            cards: dict[int, tuple] = {}
            for nid, *card in conn.execute(
                    "SELECT nid, type, queue, due, ivl, factor, reps, lapses FROM cards ORDER BY ivl"):
                cards[nid] = tuple(card)
            notes = []
            for nid, mid, flds in conn.execute("SELECT id, mid, flds FROM notes"):
                note = note_from_fields(flds.split("\x1f"), names.get(mid))
                if note is None:
                    continue
                if nid in cards:
                    note.schedule = _schedule(cards[nid], crt, now)
                notes.append(note)
        finally:
            conn.close()
    return notes


def parse_anki_file(data: bytes, filename: str) -> list[AnkiNote]:
    if filename.lower().endswith((".apkg", ".colpkg")) or data[:2] == b"PK":
        return parse_package(data)
    return parse_text(data)


# ---------- Запись в базу ----------

IMPORT_PER_DAY = 15  # сколько просроченных/новых карточек из Anki ставить на один день


@dataclass
class ImportReport:
    added: int = 0
    already: int = 0
    with_progress: int = 0
    skipped: list[str] = field(default_factory=list)  # слова без перевода


async def import_notes(session: AsyncSession, user: User, notes: list[AnkiNote],
                       now: datetime | None = None) -> ImportReport:
    """Добавляет слова в «Мои слова». Слова, которые уже есть в боте, не трогаем.

    Карточки с прогрессом из Anki ставим на их дату. Просроченные и новые
    раскладываем по IMPORT_PER_DAY в день, чтобы не получить 100 карточек разом.
    """
    from bot.services.words import add_custom_word  # локальный импорт, чтобы не было циклов

    now = now or utcnow()
    report = ImportReport()
    queue: list[tuple[UserWord, AnkiNote]] = []
    for note in notes:
        if not note.ru:
            report.skipped.append(note.en)
            continue
        card, created = await add_custom_word(session, user, note.en, note.ru, note.example, topic="anki")
        if not created:
            report.already += 1
            continue
        report.added += 1
        sched = note.schedule
        if sched is not None:
            report.with_progress += 1
            card.interval_days, card.ease = sched.interval_days, sched.ease
            card.repetitions, card.lapses = sched.repetitions, sched.lapses
        if sched is not None and sched.due_at is not None and sched.due_at > now:
            card.due_at = sched.due_at
        else:
            queue.append((card, note))

    # Сначала просроченные повторения (самые давние первыми), потом новые слова
    queue.sort(key=lambda cn: (cn[1].schedule is None,
                               cn[1].schedule.due_at if cn[1].schedule and cn[1].schedule.due_at else now))
    for i, (card, _) in enumerate(queue):
        card.due_at = now + timedelta(days=i // IMPORT_PER_DAY)
    await session.flush()
    return report
