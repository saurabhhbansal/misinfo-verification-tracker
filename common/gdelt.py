"""GDELT DOC 2.0 API client (free, no key). Used by module 2 (news evidence) and module 3 (coverage timeline).

The server asks for at most one request every 5 seconds; we enforce that with a global lock.
Docs: https://blog.gdeltproject.org/doc-2-0-updates-1-5-year-searching-and-updated-mobile-interface/
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

from common import config

log = logging.getLogger(__name__)
URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MIN_INTERVAL = 5.5
_lock = threading.Lock()
_last = 0.0
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 3600


def _get(params: dict, retries: int = 2) -> dict:
    key = repr(sorted(params.items()))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    data = _fetch(params, retries)
    if data:
        _cache[key] = (time.time(), data)
    return data


def _fetch(params: dict, retries: int) -> dict:
    global _last
    with _lock:
        for attempt in range(retries):
            wait = MIN_INTERVAL - (time.time() - _last)
            if wait > 0:
                time.sleep(wait)
            try:
                r = httpx.get(URL, params={**params, "format": "json"}, headers=config.HTTP_HEADERS, timeout=30)
            except httpx.HTTPError as e:
                log.info("GDELT request failed: %s", e)
                return {}
            finally:
                _last = time.time()
            if r.status_code != 429:
                break
            time.sleep(10 * (attempt + 1))  # server-side limit remembers recent calls from this IP
    if r.status_code != 200 or not r.text.lstrip().startswith("{"):
        log.info("GDELT returned %s: %s", r.status_code, r.text[:120])
        return {}
    try:
        return r.json()
    except ValueError:
        return {}


def _q(query: str) -> str:
    # GDELT rejects very short words and some punctuation; keep a compact keyword query.
    words = [w for w in "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in query).split() if len(w) > 2]
    return " ".join(words[:8])


def _window(timespan: str, start=None, end=None) -> dict:
    """GDELT accepts either a relative `timespan` or absolute start/end (YYYYMMDDHHMMSS, from 2017 on)."""
    if start and end:
        return {"startdatetime": start.strftime("%Y%m%d%H%M%S"), "enddatetime": end.strftime("%Y%m%d%H%M%S")}
    return {"timespan": timespan}


def articles(query: str, timespan: str = "3months", max_records: int = 25, country: str | None = None,
             start=None, end=None) -> list[dict]:
    q = _q(query)
    if not q:
        return []
    if country:
        q += f" sourcecountry:{country}"
    data = _get({"query": q, "mode": "artlist", "maxrecords": max_records, "sort": "hybridrel",
                 **_window(timespan, start, end)})
    return data.get("articles", [])


def timeline(query: str, timespan: str = "1month", start=None, end=None) -> list[dict]:
    """Daily/hourly article-volume timeline: [{'date': 'YYYYMMDDTHHMMSSZ', 'value': float}, ...]."""
    q = _q(query)
    if not q:
        return []
    data = _get({"query": q, "mode": "timelinevolraw", **_window(timespan, start, end)})
    tl = data.get("timeline") or []
    return tl[0].get("data", []) if tl else []
