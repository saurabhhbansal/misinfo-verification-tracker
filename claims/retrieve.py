"""Evidence retrieval for one claim: query all sources, dedupe, re-rank with multilingual embeddings."""
from __future__ import annotations

import logging
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
        "GDELT news": lambda: web.news_gdelt(q0),
    }
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


def find_evidence(claim: Claim) -> tuple[list[Evidence], list[str]]:
    raw, used = _gather(claim)
    return rerank(claim, _dedupe(raw)), used
