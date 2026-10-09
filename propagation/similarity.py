"""Near-duplicate / same-content matching between the checked post and candidate posts.

Two complementary signals (research.md §6):
 * MinHash Jaccard on character 4-gram shingles — catches copy-paste with small edits (Pacheco et al., arXiv 2001.05658)
 * Multilingual embedding cosine — catches paraphrases and Hindi/English versions of the same message
"""
from __future__ import annotations

import re

from datasketch import MinHash

from common import embed

NUM_PERM = 128
JACCARD_MATCH = 0.5
COSINE_MATCH = 0.87  # multilingual-e5: unrelated texts typically score ~0.70-0.80


def _shingles(text: str, k: int = 4) -> set[str]:
    t = re.sub(r"\s+", " ", re.sub(r"https?://\S+|[#@]\w+", " ", text.lower())).strip()
    return {t[i:i + k] for i in range(max(1, len(t) - k + 1))}


def minhash(text: str) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    for s in _shingles(text):
        m.update(s.encode("utf-8"))
    return m


def jaccard(a: str, b: str) -> float:
    return minhash(a).jaccard(minhash(b))


def score_candidates(reference: str, candidates: list[str]) -> list[tuple[float, float]]:
    """Return [(jaccard, cosine)] for each candidate vs the reference text."""
    if not candidates:
        return []
    ref_m = minhash(reference)
    cos = embed.similarity([reference], candidates)[0]
    return [(ref_m.jaccard(minhash(c)), float(s)) for c, s in zip(candidates, cos)]


def score_against_many(references: list[str], candidates: list[str]) -> list[tuple[float, float]]:
    """Best (jaccard, cosine) of each candidate against any of the reference texts."""
    if not references or not candidates:
        return [(0.0, 0.0)] * len(candidates)
    per_ref = [score_candidates(r, candidates) for r in references]
    return [(max(s[i][0] for s in per_ref), max(s[i][1] for s in per_ref)) for i in range(len(candidates))]


def is_match(jac: float, cos: float) -> bool:
    return jac >= JACCARD_MATCH or cos >= COSINE_MATCH


def combined(jac: float, cos: float) -> float:
    """Single 0..1 score for display: rescale cosine so 0.75->0 and 1.0->1."""
    return round(max(jac, min(1.0, max(0.0, (cos - 0.75) / 0.25))), 3)
