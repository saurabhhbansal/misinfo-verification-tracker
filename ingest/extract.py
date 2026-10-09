"""Module 1 entry point: link (or uploaded file) -> ContentBundle with caption, transcript and OCR text."""
from __future__ import annotations

import logging
from pathlib import Path

from common import config
from common.models import ContentBundle
from ingest import downloaders as dl
from ingest import ocr, router, stt

log = logging.getLogger(__name__)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".opus"}


class UnsupportedPlatform(Exception):
    pass


def fetch(url: str, check_id: str) -> ContentBundle:
    """Download the post (no text extraction yet)."""
    info = router.detect(url)
    out_dir = config.MEDIA_DIR / check_id
    if info.support == "unsupported":
        raise UnsupportedPlatform(info.reason)

    if info.name == "x":
        tid = router.tweet_id(url)
        if not tid:
            raise dl.DownloadError("Could not find a post id in this X link (expected …/status/<id>).")
        bundle = dl.x_fetch(url, tid, out_dir)
    elif info.name == "reddit":
        bundle = dl.reddit_oembed(url)
    elif info.name == "image":
        bundle = dl.image_fetch(url, out_dir)
    elif info.name in ("youtube", "facebook", "media"):
        bundle = dl.ytdlp_download(url, out_dir, info.name)
    else:  # generic web page: maybe a video page, else an article
        try:
            bundle = dl.ytdlp_download(url, out_dir, "web")
        except dl.DownloadError:
            bundle = dl.article_fetch(url)
    if info.reason and info.support == "partial":
        bundle.notes.append(info.reason)
    return bundle


def extract_text(bundle: ContentBundle, do_stt: bool = True, do_ocr: bool = True) -> ContentBundle:
    """Run speech-to-text and OCR on the downloaded media files."""
    transcripts, langs = [], []
    for p in bundle.media_paths:
        ext = Path(p).suffix.lower()
        if do_stt and ext in VIDEO_EXT | AUDIO_EXT:
            text, lang = stt.transcribe(p)
            if text:
                transcripts.append(text)
                langs.append(lang)
        if do_ocr and ext in VIDEO_EXT:
            bundle.ocr_lines.extend(ocr.ocr_video(p))
        elif do_ocr and ext in IMAGE_EXT:
            bundle.ocr_lines.extend(ocr.ocr_image(p))
    bundle.transcript = "\n".join(transcripts)
    bundle.transcript_lang = ",".join(sorted(set(langs)))
    bundle.ocr_lines = ocr.dedupe_lines(bundle.ocr_lines)
    if not bundle.full_text():
        bundle.notes.append("No text, speech or on-screen text could be extracted from this post.")
    return bundle


def from_upload(path: Path, original_name: str, caption: str = "") -> ContentBundle:
    """Bundle for a user-uploaded file (fallback for unsupported platforms)."""
    return ContentBundle(url=f"upload://{original_name}", platform="upload", title=original_name,
                         caption=caption, media_paths=[str(path)])
