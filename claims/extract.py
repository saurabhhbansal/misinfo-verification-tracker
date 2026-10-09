"""Claim extraction: rule tagging + (optional) LLM decomposition, Loki-style.

Ref: Loki (arXiv 2410.01794) — Decomposer → Check-worthiness → Query generator.
"""
from __future__ import annotations

import logging

from claims import rules
from common import config, llm
from common.models import Claim, ContentBundle

log = logging.getLogger(__name__)
RULES_MAX_CLAIMS = 3  # without an LLM, keep only the strongest candidates

SYSTEM = """You are a fact-checking assistant for Indian social media (Hindi, English, Hinglish).
From the post content, extract the CHECKABLE factual claims: statements that can be verified true or false
with public evidence. Prioritise claims with numbers, statistics, dates, named people/organisations, and
attributions ("according to the government", "WHO says"). Ignore opinions, jokes, questions, greetings and
calls to action. Each claim must be atomic and self-contained (resolve pronouns; add who/where/when if known
from the post). Do NOT judge truth. Do NOT invent claims not present in the content.

Return JSON: {"claims": [{"text": "<claim as stated, original language>",
 "text_en": "<faithful English version>",
 "kind": "numeric|date|attribution|entity|other",
 "source": "title|caption|speech|ocr",
 "queries": ["<short web search query in English>", "<optional second query, Hindi if the topic is Indian>"]}]}
Return at most MAX claims, most check-worthy first. Return {"claims": []} if nothing is checkable."""


def _sections(b: ContentBundle) -> list[tuple[str, str]]:
    secs = [("title", b.title), ("caption", b.caption), ("speech", b.transcript), ("ocr", "\n".join(b.ocr_lines))]
    return [(s, t) for s, t in secs if t and t.strip()]


def rule_candidates(b: ContentBundle) -> list[dict]:
    cands = []
    for src, text in _sections(b):
        cands.extend(rules.candidates(text, src))
    if b.platform in ("youtube", "facebook"):
        for c in cands:  # video descriptions are mostly channel boilerplate
            if c["source"] == "caption":
                c["score"] -= 0.25
    cands.sort(key=lambda c: -c["score"])
    # dedupe near-identical sentences (e.g. same text in caption and OCR)
    seen, out = set(), []
    for c in cands:
        k = "".join(ch for ch in c["text"].lower() if ch.isalnum())[:80]
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def extract_claims(b: ContentBundle, max_claims: int | None = None) -> tuple[list[Claim], str]:
    """Return (claims, method) where method is 'llm' or 'rules'."""
    max_claims = max_claims or config.MAX_CLAIMS
    cands = rule_candidates(b)
    if llm.available():
        try:
            return _llm_extract(b, cands, max_claims), "llm"
        except Exception as e:
            log.warning("LLM extraction failed, falling back to rules: %s", e)
    limit = min(max_claims, RULES_MAX_CLAIMS)
    claims = [Claim(text=c["text"], text_en="", kind=c["kind"], source=c["source"], quantities=c["quantities"])
              for c in cands if c["score"] >= 0.3][:limit]
    return claims, "rules"


def _llm_extract(b: ContentBundle, cands: list[dict], max_claims: int) -> list[Claim]:
    content = "\n\n".join(f"[{src.upper()}]\n{text[:4000]}" for src, text in _sections(b))
    hints = "\n".join(f"- ({c['kind']}) {c['text']}" for c in cands[:15]) or "(none)"
    user = (f"Post platform: {b.platform}; author: {b.author or 'unknown'}; date: {b.published or 'unknown'}\n\n"
            f"POST CONTENT:\n{content}\n\nRULE-BASED HINTS (sentences with numbers/dates/attributions):\n{hints}")
    data = llm.chat_json(SYSTEM.replace("MAX", str(max_claims)), user)
    claims = []
    for c in (data.get("claims") or [])[:max_claims]:
        text = (c.get("text") or "").strip()
        if not text or rules.is_junk(text, min_words=3):  # LLM output is already curated
            continue
        claims.append(Claim(
            text=text,
            text_en=(c.get("text_en") or "").strip(),
            kind=c.get("kind") if c.get("kind") in ("numeric", "date", "attribution", "entity", "other") else "other",
            source=c.get("source") if c.get("source") in ("title", "caption", "speech", "ocr") else "caption",
            quantities=rules.quantities(text),
            queries=[q for q in (c.get("queries") or []) if isinstance(q, str)][:2],
        ))
    return claims
