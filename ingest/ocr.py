"""OCR for images and video frames with EasyOCR (Hindi + English, CPU)."""
from __future__ import annotations

import logging
import re
from functools import lru_cache

import numpy as np

from common import config

log = logging.getLogger(__name__)
MIN_CONF = 0.4
MAX_FRAMES = config.OCR_MAX_FRAMES
FRAME_DIFF_BITS = 10  # dHash bits that must differ before a frame is OCR'd again


@lru_cache(maxsize=1)
def _reader():
    import easyocr
    return easyocr.Reader(["hi", "en"], gpu=False, verbose=False)


def _dhash(gray: np.ndarray) -> int:
    """Difference hash: 64-bit fingerprint used to skip near-identical frames."""
    import cv2
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _ocr_array(img: np.ndarray) -> list[str]:
    out = []
    for _box, text, conf in _reader().readtext(img, detail=1, paragraph=False):
        text = text.strip()
        if conf >= MIN_CONF and len(text) >= 3:
            out.append(text)
    return out


def ocr_image(path: str) -> list[str]:
    import cv2
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)  # unicode-safe on Windows
    if img is None:
        return []
    return dedupe_lines(_ocr_array(img))


def ocr_video(path: str, every_s: float | None = None) -> list[str]:
    """OCR up to MAX_FRAMES frames spread evenly over the video, skipping frames that look like the last one.

    EasyOCR takes ~5 s per frame on a laptop CPU, so the frame budget, not the video length, sets the cost.
    """
    import cv2
    every_s = every_s or config.OCR_EVERY_SECONDS
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or int(fps * 60)
    idxs = list(range(0, total, max(1, int(fps * every_s))))
    if len(idxs) > MAX_FRAMES:
        idxs = [idxs[round(i * (len(idxs) - 1) / (MAX_FRAMES - 1))] for i in range(MAX_FRAMES)]
    lines, last_hash = [], None
    for idx in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            break
        h = _dhash(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        if last_hash is None or _hamming(h, last_hash) > FRAME_DIFF_BITS:
            lines.extend(_ocr_array(frame))
            last_hash = h
    cap.release()
    return dedupe_lines(lines)


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s.lower())


def dedupe_lines(lines: list[str]) -> list[str]:
    seen, out = set(), []
    for line in lines:
        k = _norm(line)
        if k and k not in seen:
            seen.add(k)
            out.append(line)
    return out
