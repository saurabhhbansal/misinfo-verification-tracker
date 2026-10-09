"""Module 3 entry point: build the propagation summary for a checked post."""
from __future__ import annotations

import logging
import re

import numpy as np

from common import gdelt
from common.models import Claim, ContentBundle, Post
from propagation import burst, search, similarity

log = logging.getLogger(__name__)

_STOP = set("the a an and or of to in on for is are was were be this that with from by at as it its has have had "
            "will can not but you your our they he she we i".split())


def build_query(bundle: ContentBundle, claims: list[Claim]) -> str:
    """Short keyword query from the post title or the top claim."""
    base = bundle.title if bundle.platform in ("youtube", "web") and bundle.title else ""
    if not base and claims:
        base = claims[0].query_text()
    if not base:
        base = (bundle.caption or bundle.transcript)[:200]
    words = [w for w in re.findall(r"\w+", base, re.U) if w.lower() not in _STOP and len(w) > 2]
    return " ".join(words[:10])


def reference_text(bundle: ContentBundle, claims: list[Claim]) -> str:
    parts = [bundle.title, bundle.caption[:500]] + [c.query_text() for c in claims[:3]]
    return " ".join(p for p in parts if p)[:1500]


def analyse(bundle: ContentBundle, claims: list[Claim]) -> dict:
    query = build_query(bundle, claims)
    report = {"query": query, "sources_used": [], "sources_unavailable": [], "matches": [], "timeline": [],
              "news_timeline": [], "burst": {}, "clusters": [], "level": "insufficient", "explanation": "",
              "original_stats": bundle.stats}
    if not query:
        report["explanation"] = "No text to search for."
        return report

    candidates: list[Post] = []
    if search.youtube_available():
        candidates += search.youtube(query)
        report["sources_used"].append("YouTube Data API")
    else:
        report["sources_unavailable"].append("YouTube (set GOOGLE_API_KEY)")
    candidates += search.news(query)
    report["sources_used"].append("GDELT news")
    report["sources_unavailable"] += ["X/Twitter search (paid API, not used)", "Reddit search (API approval needed)",
                                      "Instagram/Facebook search (no public API)"]

    # drop the original post itself
    candidates = [p for p in candidates if p.url.rstrip("/") != bundle.url.rstrip("/")
                  and p.post_id not in bundle.url]

    ref = reference_text(bundle, claims)
    scores = similarity.score_candidates(ref, [p.text for p in candidates])
    matches = []
    for p, (jac, cos) in zip(candidates, scores):
        if similarity.is_match(jac, cos):
            p.similarity = similarity.combined(jac, cos)
            matches.append(p)
    matches.sort(key=lambda p: p.published)
    report["matches"] = [vars(p) for p in matches]

    report["timeline"] = burst.buckets(matches, hours=6)
    report["burst"] = burst.burst_stats(report["timeline"])
    if len(matches) >= 2:
        texts = [p.text for p in matches]
        mh = [similarity.minhash(t) for t in texts]
        jac = np.array([[a.jaccard(b) for b in mh] for a in mh])
        report["clusters"] = burst.coordination(matches, jac, sim_threshold=0.8, time_window_s=3600)
    report["level"], report["explanation"] = burst.assess(report["burst"], report["clusters"], len(matches))

    try:
        report["news_timeline"] = [{"date": d.get("date"), "value": d.get("value")}
                                   for d in gdelt.timeline(query, timespan="1month")]
    except Exception as e:
        log.info("GDELT timeline failed: %s", e)
    return report
