"""Find posts similar to the checked content on platforms that allow it today (see research.md §6).

* YouTube Data API v3 (free key; search.list = 100 quota units of 10,000/day)
* GDELT news articles (free, no key) — treated as 'posts' by news outlets
X and Reddit search are NOT available (paid / approval-gated) and are reported as such.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from common import config, gdelt
from common.models import Post

log = logging.getLogger(__name__)
YT = "https://www.googleapis.com/youtube/v3"


def youtube_available() -> bool:
    return bool(config.GOOGLE_API_KEY)


def youtube(query: str, days: int = 90, max_results: int = 25) -> list[Post]:
    if not youtube_available() or not query:
        return []
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        r = httpx.get(f"{YT}/search", timeout=20, params={
            "part": "snippet", "q": query[:200], "type": "video", "maxResults": max_results,
            "publishedAfter": after, "order": "relevance", "key": config.GOOGLE_API_KEY})
        r.raise_for_status()
        items = r.json().get("items", [])
        ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
        stats = {}
        if ids:
            s = httpx.get(f"{YT}/videos", timeout=20, params={
                "part": "statistics", "id": ",".join(ids), "key": config.GOOGLE_API_KEY})
            if s.status_code == 200:
                stats = {v["id"]: v.get("statistics", {}) for v in s.json().get("items", [])}
    except httpx.HTTPError as e:
        log.warning("YouTube search failed: %s", e)
        return []
    out = []
    for it in items:
        sn, vid = it.get("snippet", {}), it.get("id", {}).get("videoId")
        if not vid:
            continue
        st = stats.get(vid, {})
        out.append(Post(platform="youtube", post_id=vid, author=sn.get("channelTitle", ""),
                        published=sn.get("publishedAt", ""),
                        text=f"{sn.get('title', '')}. {sn.get('description', '')}",
                        url=f"https://www.youtube.com/watch?v={vid}",
                        stats={k: int(v) for k, v in st.items() if k in ("viewCount", "likeCount", "commentCount")}))
    return out


def news(query: str, timespan: str = "1month") -> list[Post]:
    out = []
    for a in gdelt.articles(query, timespan=timespan, max_records=50):
        try:
            ts = datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
        out.append(Post(platform="news", post_id=a.get("url", ""), author=a.get("domain", ""), published=ts,
                        text=a.get("title", ""), url=a.get("url", "")))
    return out
