"""Identify which platform a link belongs to and whether we can support it.

Support levels reflect what we verified on 9 Oct 2026 (see docs/research.md §0).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class PlatformInfo:
    name: str
    support: str  # supported | partial | unsupported
    reason: str = ""


PLATFORMS = {
    "youtube": PlatformInfo("youtube", "supported"),
    "x": PlatformInfo("x", "supported", "Post text via X's public embed endpoint; video via yt-dlp. "
                                        "Searching X for similar posts needs the paid X API (not used)."),
    "facebook": PlatformInfo("facebook", "partial", "Only public videos can be downloaded without login."),
    "reddit": PlatformInfo("reddit", "partial", "Reddit blocks anonymous access (HTTP 403) and API access needs "
                                                "manual approval; only the title and author are available. "
                                                "Upload the media file for a full check."),
    "instagram": PlatformInfo("instagram", "unsupported", "Instagram requires login to fetch posts; logging in "
                                                          "with an account is outside this project's rules. "
                                                          "Download the post yourself and use 'Upload a file'."),
    "image": PlatformInfo("image", "supported"),
    "media": PlatformInfo("media", "supported"),
    "web": PlatformInfo("web", "supported", "Generic page: we try the video downloader, then article-text extraction."),
}

_HOSTS = [
    (r"(^|\.)(youtube\.com|youtu\.be)$", "youtube"),
    (r"(^|\.)(twitter\.com|x\.com)$", "x"),
    (r"(^|\.)(facebook\.com|fb\.watch|fb\.com)$", "facebook"),
    (r"(^|\.)(reddit\.com|redd\.it)$", "reddit"),
    (r"(^|\.)(instagram\.com|instagr\.am)$", "instagram"),
]
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
_MEDIA_EXT = (".mp4", ".mov", ".webm", ".mkv", ".mp3", ".m4a", ".wav", ".ogg")


def detect(url: str) -> PlatformInfo:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Please enter a full http(s) link.")
    host = parsed.netloc.lower().split(":")[0]
    for pattern, name in _HOSTS:
        if re.search(pattern, host):
            return PLATFORMS[name]
    path = parsed.path.lower()
    if path.endswith(_IMAGE_EXT):
        return PLATFORMS["image"]
    if path.endswith(_MEDIA_EXT):
        return PLATFORMS["media"]
    return PLATFORMS["web"]


def tweet_id(url: str) -> str | None:
    m = re.search(r"/status(?:es)?/(\d+)", url)
    return m.group(1) if m else None
