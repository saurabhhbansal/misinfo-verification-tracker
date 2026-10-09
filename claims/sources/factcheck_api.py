"""Google Fact Check Tools API (claims:search). Free; needs GOOGLE_API_KEY.

Docs: https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search
Returns existing fact-checks (ClaimReview) incl. Indian IFCN signatories (Alt News, BOOM, Factly, ...).
"""
from __future__ import annotations

import logging

import httpx

from common import config
from common.models import Evidence

log = logging.getLogger(__name__)
URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


def available() -> bool:
    return bool(config.GOOGLE_API_KEY)


def search(query: str, language: str | None = None, page_size: int = 10) -> list[Evidence]:
    if not available():
        return []
    params = {"query": query[:300], "pageSize": page_size, "key": config.GOOGLE_API_KEY}
    if language:
        params["languageCode"] = language
    try:
        r = httpx.get(URL, params=params, timeout=20)
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Fact Check API error: %s", e)
        return []
    out = []
    for c in r.json().get("claims", []):
        for rev in c.get("claimReview", []):
            out.append(Evidence(
                url=rev.get("url", ""),
                title=rev.get("title") or c.get("text", ""),
                snippet=f"Claim reviewed: \"{c.get('text', '')}\" (claimant: {c.get('claimant', 'unknown')}). "
                        f"Rating: {rev.get('textualRating', '')}.",
                source_type="factcheck",
                publisher=(rev.get("publisher") or {}).get("name", ""),
                published=rev.get("reviewDate"),
                rating=rev.get("textualRating", ""),
            ))
    return [e for e in out if e.url]
