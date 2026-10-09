"""Parse quantities ("₹2 lakh crore", "45%", "3.5 million", "२० करोड़") and compare claim vs evidence numbers."""
from __future__ import annotations

import re

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
MULT = {
    "thousand": 1e3, "हजार": 1e3, "हज़ार": 1e3,
    "lakh": 1e5, "lakhs": 1e5, "लाख": 1e5,
    "million": 1e6,
    "crore": 1e7, "crores": 1e7, "करोड़": 1e7, "करोड": 1e7,
    "billion": 1e9, "अरब": 1e9,
    "trillion": 1e12,
}
PERCENT = ("%", "percent", "per cent", "प्रतिशत", "फीसदी")
_Q_RE = re.compile(
    r"(?<![A-Za-z\d.,\-])(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<u1>%|percent|per cent|प्रतिशत|फीसदी|thousand|हजार|हज़ार|lakhs?|लाख|million|"
    r"crores?|करोड़|करोड|billion|अरब|trillion)?(?:\s*(?P<u2>crores?|करोड़|करोड|million|billion))?",
    re.I,
)
_YEAR = re.compile(r"^(1[89]\d\d|20\d\d)$")


def parse(text: str) -> list[tuple[float, str]]:
    """Return list of (value, unit_class) where unit_class is 'percent' or 'count'. Years are skipped."""
    out = []
    for m in _Q_RE.finditer((text or "").translate(_DEV_DIGITS)):
        raw = m.group("num").replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        u1 = (m.group("u1") or "").lower()
        u2 = (m.group("u2") or "").lower()
        if not u1 and _YEAR.match(raw):
            continue
        if u1 in PERCENT:
            out.append((v, "percent"))
            continue
        v *= MULT.get(u1, 1.0) * MULT.get(u2, 1.0)
        out.append((v, "count"))
    return out


def compare(claim: str, evidence_texts: list[str], tol: float = 0.1) -> str:
    """Human-readable note on whether numbers in the claim appear in the evidence (within ±tol)."""
    cq = parse(claim)
    if not cq:
        return ""
    eq = [q for t in evidence_texts for q in parse(t)]
    if not eq:
        return "Claim contains numbers, but the evidence snippets contain no comparable figures."
    notes = []
    for v, unit in cq:
        same_unit = [e for e, u in eq if u == unit]
        if not same_unit:
            continue
        best = min(same_unit, key=lambda e: abs(e - v) / max(abs(v), 1e-9))
        rel = abs(best - v) / max(abs(v), 1e-9)
        shown = f"{v:g}{'%' if unit == 'percent' else ''}"
        if rel <= tol:
            notes.append(f"{shown} matches evidence ({best:g}).")
        else:
            notes.append(f"{shown} not found; closest evidence figure is {best:g} ({rel:.0%} off).")
    return " ".join(notes)
