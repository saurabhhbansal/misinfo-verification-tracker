"""Evidence retrieval for one claim: query all sources, dedupe, re-rank with multilingual embeddings."""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor

from claims.sources import factcheck_api, feeds, web
from common import embed
from common.models import Claim, Evidence

log = logging.getLogger(__name__)

MIN_RELEVANCE = 0.80   # e5 cosine; below this a passage is treated as unrelated (unrelated pairs score ~0.75-0.80)
TOP_K = 8
SOURCE_BONUS = {"factcheck": 0.02, "govt": 0.015, "news": 0.0, "web": 0.0}


def _gather(claim: Claim) -> tuple[list[Evidence], list[str]]:
    """Call every configured source. Returns (evidence, list of sources used)."""
    queries = claim.search_queries()
    q0 = queries[0]
    jobs = {
        "Indian fact-checkers (RSS search)": lambda: [e for q in queries[:2] for e in feeds.search_factcheckers(q)],
        "PIB / fact-check latest feeds": feeds.latest_items,
    }
    if not web.tavily_available():  # GDELT is rate-limited (1 req / 5 s); only needed without a web-search key
        jobs["GDELT news"] = lambda: web.news_gdelt(q0)
    if factcheck_api.available():
        jobs["Google Fact Check API"] = lambda: [e for q in queries for e in factcheck_api.search(q)]
    if web.tavily_available():
        jobs["Web search (Tavily)"] = lambda: web.tavily(q0)
        jobs["Govt sites (Tavily)"] = lambda: web.tavily(q0, govt_only=True)
    results, used = [], []
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {name: ex.submit(fn) for name, fn in jobs.items()}
        for name, f in futs.items():
            try:
                items = f.result(timeout=90)
                results.extend(items)
                used.append(name)
            except Exception as e:
                log.warning("source %s failed: %s", name, e)
    return results, used


def _dedupe(items: list[Evidence]) -> list[Evidence]:
    seen, out = set(), []
    for e in items:
        k = e.url.split("?")[0].rstrip("/").lower()
        if k and k not in seen:
            seen.add(k)
            out.append(e)
    return out


def rerank(claim: Claim, items: list[Evidence], top_k: int = TOP_K, min_rel: float = MIN_RELEVANCE) -> list[Evidence]:
    if not items:
        return []
    texts = [f"{e.title}. {e.snippet}"[:1000] for e in items]
    sims = embed.similarity([claim.query_text()] + ([claim.text] if claim.text_en else []), texts).max(axis=0)
    for e, s in zip(items, sims):
        e.score = float(s) + SOURCE_BONUS.get(e.source_type, 0)
    ranked = sorted((e for e in items if e.score >= min_rel), key=lambda e: -e.score)
    return ranked[:top_k]


def _norm_url(u: str) -> str:
    u = u.split("#")[0].lower().replace("://www.", "://").replace("://m.", "://")
    return u.rstrip("/")


def same_post(url: str, post_url: str | None) -> bool:
    """True if `url` is the post being checked (would be circular evidence)."""
    if not post_url:
        return False
    if _norm_url(url).split("&")[0] == _norm_url(post_url).split("&")[0]:
        return True
    m = re.search(r"(?:v=|youtu\.be/|shorts/|status/)([\w-]{6,})", post_url)
    return bool(m and m.group(1) in url)


def find_evidence(claim: Claim, post_url: str | None = None) -> tuple[list[Evidence], list[str]]:
    raw, used = _gather(claim)
    raw = [e for e in raw if not same_post(e.url, post_url)]
    return rerank(claim, _dedupe(raw)), used
