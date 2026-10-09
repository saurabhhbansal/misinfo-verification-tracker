"""News (GDELT, free) and general web search (Tavily free tier, 1,000 credits/month)."""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from common import config, gdelt
from common.models import Evidence

log = logging.getLogger(__name__)
GOVT_DOMAINS = ["pib.gov.in", "gov.in", "nic.in", "data.gov.in", "rbi.org.in", "who.int", "censusindia.gov.in"]


def _gdelt_date(s: str | None) -> str | None:
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").isoformat() + "Z"
    except (TypeError, ValueError):
        return None


def news_gdelt(query: str, max_records: int = 15) -> list[Evidence]:
    out = []
    for a in gdelt.articles(query, timespan="3months", max_records=max_records):
        out.append(Evidence(url=a.get("url", ""), title=a.get("title", ""), snippet=a.get("title", ""),
                            source_type="news", publisher=a.get("domain", ""),
                            published=_gdelt_date(a.get("seendate"))))
    return [e for e in out if e.url]


def tavily_available() -> bool:
    return bool(config.TAVILY_API_KEY)


def tavily(query: str, govt_only: bool = False, max_results: int = 5) -> list[Evidence]:
    if not tavily_available():
        return []
    body = {"query": query[:350], "max_results": max_results, "search_depth": "basic", "include_answer": False}
    if govt_only:
        body["include_domains"] = GOVT_DOMAINS
    try:
        r = httpx.post("https://api.tavily.com/search", json=body,
                       headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"}, timeout=30)
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Tavily error: %s", e)
        return []
    out = []
    for res in r.json().get("results", []):
        url = res.get("url", "")
        st = "govt" if any(d in url for d in GOVT_DOMAINS) else "web"
        out.append(Evidence(url=url, title=res.get("title", ""), snippet=(res.get("content") or "")[:800],
                            source_type=st, publisher=url.split("/")[2] if "//" in url else "",
                            published=res.get("published_date")))
    return out
