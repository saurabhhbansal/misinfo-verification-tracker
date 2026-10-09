"""Download public post content. Never logs in, never uses cookies."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from common import config
from common.models import ContentBundle

log = logging.getLogger(__name__)


class DownloadError(Exception):
    pass


def _iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- yt-dlp
def _deno_path() -> str | None:
    try:
        import deno
        return deno.find_deno_bin()
    except Exception:
        return None  # yt-dlp then looks for `deno` on PATH


def ytdlp_download(url: str, out_dir: Path, platform: str, download: bool = True) -> ContentBundle:
    """Video/audio posts (YouTube, X video, Facebook public video, many others)."""
    import imageio_ffmpeg
    import yt_dlp

    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        # small single file with audio is enough for STT + OCR
        "format": "bv*[height<=480]+ba/b[height<=480]/b",
        "merge_output_format": "mp4",
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "skip_download": not download,
        "socket_timeout": 30,
        # YouTube needs a JS runtime (yt-dlp EJS); use the Deno binary installed by the `deno` pip package
        "js_runtimes": {"deno": {"path": _deno_path()}},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("_type") == "playlist":
                raise DownloadError("Playlists are not supported; paste a single post link.")
            duration = info.get("duration") or 0
            if download and duration > config.MAX_MEDIA_SECONDS:
                raise DownloadError(f"Media is {duration:.0f}s long; limit is {config.MAX_MEDIA_SECONDS}s.")
            if download:
                info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e).replace("ERROR: ", "")) from e

    media = []
    for req in info.get("requested_downloads") or []:
        if req.get("filepath"):
            media.append(req["filepath"])
    return ContentBundle(
        url=url,
        platform=platform,
        title=info.get("title") or "",
        caption=info.get("description") or "",
        author=info.get("uploader") or info.get("channel") or "",
        published=_iso(info.get("timestamp")) or _upload_date(info.get("upload_date")),
        stats={k: info.get(k) for k in ("view_count", "like_count", "comment_count", "repost_count")
               if info.get(k) is not None},
        media_paths=media,
    )


def _upload_date(d: str | None) -> str | None:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- X / Twitter
X_EMBED = "https://cdn.syndication.twimg.com/tweet-result"


def x_fetch(url: str, tid: str, out_dir: Path) -> ContentBundle:
    """Tweet text + photos via the public embed endpoint used by X's own embedded-tweet widget.

    Undocumented: may change without notice (see research.md §1.3).
    """
    r = httpx.get(X_EMBED, params={"id": tid, "token": "a", "lang": "en"},
                  headers=config.HTTP_HEADERS, timeout=20)
    if r.status_code != 200 or not r.text.strip().startswith("{"):
        raise DownloadError(f"X post not available publicly (HTTP {r.status_code}). It may be deleted or protected.")
    d = r.json()
    if d.get("__typename") == "TweetTombstone":
        raise DownloadError("X post is not viewable without login (tombstoned).")
    user = d.get("user") or {}
    b = ContentBundle(
        url=url,
        platform="x",
        caption=d.get("text", ""),
        author="@" + user.get("screen_name", "") if user.get("screen_name") else "",
        published=d.get("created_at"),
        stats={"like_count": d.get("favorite_count"), "reply_count": d.get("conversation_count")},
    )
    if d.get("quoted_tweet"):
        b.caption += "\n[quoted] " + d["quoted_tweet"].get("text", "")
    out_dir.mkdir(parents=True, exist_ok=True)
    has_video = False
    for i, m in enumerate(d.get("mediaDetails") or []):
        if m.get("type") == "photo" and m.get("media_url_https"):
            p = out_dir / f"x_{tid}_{i}.jpg"
            _download_file(m["media_url_https"], p)
            b.media_paths.append(str(p))
        elif m.get("type") in ("video", "animated_gif"):
            has_video = True
    if has_video:
        try:
            v = ytdlp_download(url, out_dir, "x")
            b.media_paths.extend(v.media_paths)
        except DownloadError as e:
            b.notes.append(f"Video in this post could not be downloaded: {e}")
    return b


# ---------------------------------------------------------------- Reddit (partial)
def reddit_oembed(url: str) -> ContentBundle:
    r = httpx.get("https://www.reddit.com/oembed", params={"url": url},
                  headers=config.HTTP_HEADERS, timeout=20, follow_redirects=True)
    if r.status_code != 200:
        raise DownloadError(f"Reddit returned HTTP {r.status_code}.")
    d = r.json()
    import re
    title = re.sub(r"<[^>]+>", " ", d.get("html", ""))
    title = re.sub(r"\s+", " ", title).strip()
    return ContentBundle(url=url, platform="reddit", title=d.get("title") or title[:300],
                         author=d.get("author_name", ""),
                         notes=["Reddit: only the title/author are available without an approved API app."])


# ---------------------------------------------------------------- articles / images
def article_fetch(url: str) -> ContentBundle:
    import trafilatura
    html = trafilatura.fetch_url(url)
    if not html:
        raise DownloadError("Could not fetch the page.")
    doc = trafilatura.bare_extraction(html, url=url, with_metadata=True, include_comments=False)
    if not doc:
        raise DownloadError("No readable text found on the page.")
    d = doc if isinstance(doc, dict) else doc.as_dict()
    return ContentBundle(url=url, platform="web", title=d.get("title") or "",
                         caption=(d.get("text") or "")[:20000], author=d.get("author") or d.get("sitename") or "",
                         published=d.get("date"))


def image_fetch(url: str, out_dir: Path) -> ContentBundle:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / ("image" + Path(url.split("?")[0]).suffix.lower())
    _download_file(url, p)
    return ContentBundle(url=url, platform="image", media_paths=[str(p)])


def _download_file(url: str, path: Path, max_bytes: int = 50_000_000):
    with httpx.stream("GET", url, headers=config.HTTP_HEADERS, timeout=60, follow_redirects=True) as r:
        if r.status_code != 200:
            raise DownloadError(f"HTTP {r.status_code} downloading {url}")
        size = 0
        with open(path, "wb") as f:
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise DownloadError("File too large.")
                f.write(chunk)
