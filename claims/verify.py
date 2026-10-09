"""Verdict for one claim given ranked evidence.

Order of methods:
 1. no relevant evidence -> unverifiable (never guess)
 2. LLM reads ALL evidence in one prompt and must cite evidence ids (survey arXiv 2407.02351: joint prompt > per-item)
 3. fallback without LLM: multilingual NLI over each passage + direct fact-check rating match
Every non-'unverifiable' verdict carries the cited evidence (enforced in common.models.Verdict).
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache

from claims import numeric
from common import config, llm
from common.models import Claim, Evidence, Verdict

log = logging.getLogger(__name__)

SYSTEM = """You are a careful fact-checker. Decide whether the CLAIM is supported or contradicted by the EVIDENCE.
Use ONLY the evidence given; do not use outside knowledge. Pay close attention to numbers, units, dates, places
and who said what. A fact-check article that rates the same claim False/Misleading counts as contradicting it.

Labels:
- "supported": evidence clearly confirms the claim (numbers match within rounding).
- "contradicted": evidence clearly shows the claim is false or materially wrong (e.g. wrong number, fake quote).
- "conflicting": relevant evidence points both ways, or the claim is partly true / missing context.
- "unverifiable": evidence is unrelated or insufficient.

Return JSON: {"label": "...", "rationale": "<2-3 sentences citing [E#]>", "cited": ["E1", ...], "confidence": 0.0-1.0}
"cited" must list the evidence ids your decision relies on; it must be empty if label is "unverifiable"."""

FALSE_WORDS = ("false", "untrue", "not true", "fake", "misleading", "incorrect", "wrong", "fabricated", "manipulated", "edited", "satire",
               "scam", "baseless", "no evidence", "unproven", "झूठ", "फर्जी", "भ्रामक", "गलत")
TRUE_WORDS = ("true", "correct", "accurate", "सच", "सही")
NLI_MIN_RELEVANCE = 0.86
MIXED_WORDS = ("partly", "half", "mixture", "missing context", "mostly", "exaggerat", "needs context")


def rating_to_label(rating: str) -> str | None:
    r = rating.lower()
    if any(w in r for w in MIXED_WORDS):
        return "conflicting"
    if any(w in r for w in FALSE_WORDS):
        return "contradicted"
    if any(w in r for w in TRUE_WORDS):
        return "supported"
    return None


def _fmt(i: int, e: Evidence) -> str:
    extra = f" | rating: {e.rating}" if e.rating else ""
    return (f"[E{i}] ({e.source_type}; {e.publisher}; {e.published or 'date unknown'}{extra})\n"
            f"Title: {e.title}\nText: {e.snippet[:700]}")


def verify(claim: Claim, evidence: list[Evidence]) -> Verdict:
    if not evidence:
        return Verdict("unverifiable", "No relevant evidence was found in fact-check, government, news or web sources.",
                       method="none")
    note = numeric.compare(claim.text_en or claim.text, [f"{e.title} {e.snippet}" for e in evidence])
    if llm.available():
        try:
            v = _verify_llm(claim, evidence)
            v.numeric_note = note
            return v
        except Exception as e:
            log.warning("LLM verify failed; using NLI fallback: %s", e)
    v = _verify_nli(claim, evidence)
    v.numeric_note = note
    return v


def _verify_llm(claim: Claim, evidence: list[Evidence]) -> Verdict:
    ev_text = "\n\n".join(_fmt(i + 1, e) for i, e in enumerate(evidence))
    user = f"CLAIM: {claim.text}\n(English: {claim.text_en or claim.text})\n\nEVIDENCE:\n{ev_text}"
    data = llm.chat_json(SYSTEM, user)
    label = data.get("label", "unverifiable")
    if label not in ("supported", "contradicted", "conflicting", "unverifiable"):
        label = "unverifiable"
    ids = []
    for c in data.get("cited") or []:
        m = re.search(r"\d+", str(c))
        if m and 1 <= int(m.group()) <= len(evidence):
            ids.append(int(m.group()) - 1)
    cited = [evidence[i] for i in dict.fromkeys(ids)]
    if label == "unverifiable":
        cited = []
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    rationale = re.sub(r"\[E(\d+)\]", lambda m: f"[{m.group(1)}]", str(data.get("rationale", "")))
    return Verdict(label, rationale, evidence=cited, confidence=round(min(max(conf, 0), 1), 2), method="llm")


# ------------------------------------------------------------------ fallback (no LLM)
@lru_cache(maxsize=1)
def _nli():
    from transformers import pipeline
    return pipeline("text-classification", model=config.NLI_MODEL, device=-1, top_k=None)


def nli_scores(premise: str, hypothesis: str) -> dict:
    res = _nli()({"text": premise[:1500], "text_pair": hypothesis[:500]})
    res = res[0] if isinstance(res[0], list) else res
    return {d["label"].lower(): d["score"] for d in res}


def _verify_nli(claim: Claim, evidence: list[Evidence]) -> Verdict:
    hyp = claim.text_en or claim.text
    support, contra = [], []
    # 1. a closely matching fact-check with a clear rating is the strongest signal
    for e in evidence:
        if e.source_type == "factcheck" and e.rating and e.score >= 0.88:
            lab = rating_to_label(e.rating)
            if lab:
                return Verdict(lab, f"A fact-check by {e.publisher} rated a closely matching claim "
                                    f"\"{e.rating}\" [1].", evidence=[e], confidence=0.7, method="factcheck-match")
    # 2. NLI per passage — only on closely related passages: NLI models label unrelated text as "contradiction"
    for e in [e for e in evidence if e.score >= NLI_MIN_RELEVANCE]:
        s = nli_scores(f"{e.title}. {e.snippet}", hyp)
        if s.get("entailment", 0) > 0.7:
            support.append((s["entailment"], e))
        elif s.get("contradiction", 0) > 0.7:
            contra.append((s["contradiction"], e))
    if support and contra:
        cited = [e for _, e in sorted(support + contra, key=lambda x: -x[0])[:4]]
        return Verdict("conflicting", "Some evidence passages entail the claim and others contradict it (NLI).",
                       evidence=cited, confidence=0.4, method="nli")
    if support:
        cited = [e for _, e in sorted(support, key=lambda x: -x[0])[:3]]
        return Verdict("supported", "Evidence passages entail the claim (NLI model).", evidence=cited,
                       confidence=round(max(s for s, _ in support) * 0.8, 2), method="nli")
    if contra:
        cited = [e for _, e in sorted(contra, key=lambda x: -x[0])[:3]]
        return Verdict("contradicted", "Evidence passages contradict the claim (NLI model).", evidence=cited,
                       confidence=round(max(s for s, _ in contra) * 0.8, 2), method="nli")
    return Verdict("unverifiable", "Related articles were found but none clearly confirms or refutes the claim.",
                   method="nli")
