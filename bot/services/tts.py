"""Озвучка текста через edge-tts (бесплатные нейроголоса Microsoft).

Файлы кэшируются на диске, поэтому один и тот же текст озвучивается один раз.
"""
import hashlib
import logging
from pathlib import Path

import edge_tts
from aiogram import Bot
from aiogram.types import FSInputFile

from bot.config import get_settings

log = logging.getLogger(__name__)

# Голоса для разнообразия: американский и британский акценты
VOICES = ["en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-GB-RyanNeural"]


async def synthesize(text: str, voice: str | None = None, rate: str = "-5%") -> Path:
    settings = get_settings()
    voice = voice or settings.tts_voice
    cache_dir = Path(settings.audio_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()
    path = cache_dir / f"{key}.mp3"
    if not path.exists():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(path))
    return path


async def send_speech(
    bot: Bot, chat_id: int, text: str, caption: str | None = None,
    voice: str | None = None, rate: str = "-5%", reply_markup=None,
) -> bool:
    """Отправляет озвученный текст голосовым сообщением. Возвращает False, если озвучка не удалась."""
    try:
        path = await synthesize(text, voice=voice, rate=rate)
        await bot.send_voice(chat_id, FSInputFile(path), caption=caption, reply_markup=reply_markup)
        return True
    except Exception:
        log.exception("Не удалось озвучить текст")
        return False
