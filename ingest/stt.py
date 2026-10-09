"""Speech-to-text with faster-whisper (CPU, int8). Handles Hindi and English (auto language detection)."""
from __future__ import annotations

import logging
from functools import lru_cache

from common import config

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel
    return WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")


def transcribe(path: str) -> tuple[str, str]:
    """Return (transcript, language_code). Empty transcript if the file has no speech."""
    try:
        segments, info = _model().transcribe(path, vad_filter=True, beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
        return text, info.language if text else ""
    except Exception as e:  # e.g. file has no audio stream
        log.info("STT skipped for %s: %s", path, e)
        return "", ""
