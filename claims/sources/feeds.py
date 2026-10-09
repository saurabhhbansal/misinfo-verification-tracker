"""Indian fact-checkers and government press releases via public RSS feeds (no key).

* Search feeds (WordPress `?s=<query>&feed=rss2`) — verified working 2026-10-09 for Alt News, Factly, Vishvas News.
* Latest-items feeds for PIB (govt press releases) and other fact-checkers.
"""
from __future__ import annotations

import html
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import feedparser
import httpx

from common import config
from common.models import Evidence

log = logging.getLogger(__name__)

SEARCH_FEEDS = {  # publisher -> search feed template
    "Alt News": "https://www.altnews.in/?s={q}&feed=rss2",
    "Factly": "https://factly.in/?s={q}&feed=rss2",
    "Vishvas News": "https://www.vishvasnews.com/?s={q}&feed=rss2",
}
LATEST_FEEDS = {  # publisher -> (feed url, source_type)
    "PIB (Govt of India)": ("https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "govt"),
    "Newschecker": ("https://newschecker.in/feed", "factcheck"),
    "The Quint WebQoof": ("https://www.thequint.com/stories.rss?section=webqoof", "factcheck"),
}
_cache: dict[str, tuple[float, list[Evidence]]] = {}
CACHE_TTL = 3 * 3600


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _parse(url: str, publisher: str, source_type: str, limit: int = 10) -> list[Evidence]:
    try:
        r = httpx.get(url, headers=config.HTTP_HEADERS, timeout=20, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.info("feed %s failed: %s", publisher, e)
        return []
    feed = feedparser.parse(r.content)
    out = []
    for it in feed.entries[:limit]:
        out.append(Evidence(
            url=it.get("link", ""),
            title=_clean(it.get("title", "")),
            snippet=_clean(it.get("summary", ""))[:600],
            source_type=source_type,
            publisher=publisher,
            published=it.get("published") or it.get("updated"),
        ))
    return [e for e in out if e.url]


def search_factcheckers(query: str) -> list[Evidence]:
    q = quote_plus(query[:120])
    with ThreadPoolExecutor(max_workers=len(SEARCH_FEEDS)) as ex:
        results = ex.map(lambda kv: _parse(kv[1].format(q=q), kv[0], "factcheck"), SEARCH_FEEDS.items())
    return [e for batch in results for e in batch]


def latest_items() -> list[Evidence]:
    """Latest PIB releases + fact-checks, cached (re-ranked later against the claim)."""
    key = "latest"
    if key in _cache and time.time() - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    items = []
    for pub, (url, st) in LATEST_FEEDS.items():
        items.extend(_parse(url, pub, st, limit=30))
    _cache[key] = (time.time(), items)
    return items
