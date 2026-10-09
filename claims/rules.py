"""Rule-based check-worthiness tagging (English + Hindi). No model, fully explainable.

Used (a) as hints for the LLM extractor and (b) as the fallback extractor when no LLM key is set.
"""
from __future__ import annotations

import re

# Devanagari digits -> ASCII
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

NUMBER_RE = re.compile(
    r"(?<![A-Za-z\d.,\-])(?:₹|rs\.?|inr|\$|usd)?\s?\d[\d,]*(?:\.\d+)?\s?"
    r"(?:%|percent|per cent|प्रतिशत|फीसदी|lakh|lakhs|crore|crores|million|billion|trillion|thousand|"
    r"लाख|करोड़|करोड|हजार|हज़ार|अरब)?",
    re.I,
)
YEAR_RE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")
MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
          "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|"
          "जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर|नवंबर|दिसंबर")
DATE_RE = re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\b|\b(?:{MONTHS})\s+\d{{1,2}}\b|"
                     r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I)
ATTRIBUTION_RE = re.compile(
    r"\b(according to|as per|said|says|claimed|claims|announced|reported|report by|data from|study|survey|"
    r"official|government|govt|ministry|minister|who|world health organization|rbi|niti aayog|census|"
    r"supreme court|high court|pm|prime minister|chief minister|police)\b|"
    r"(के अनुसार|ने कहा|सरकार|मंत्रालय|मंत्री|रिपोर्ट|अध्ययन|सर्वे|प्रधानमंत्री|मुख्यमंत्री|पुलिस|अदालत)",
    re.I,
)
OPINION_RE = re.compile(r"\b(i think|i feel|in my opinion|should|must|subscribe|like and share|follow us)\b|"
                        r"(मुझे लगता|चाहिए|सब्सक्राइब|लाइक)", re.I)

_SPLIT_RE = re.compile(r"(?<=[.!?।])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    out = []
    for s in _SPLIT_RE.split(text or ""):
        s = s.strip(" -•*\t")
        if 15 <= len(s) <= 400:
            out.append(s)
    return out


def quantities(text: str) -> list[str]:
    t = text.translate(_DEV_DIGITS)
    qs = [m.group(0).strip().rstrip(",.").strip() for m in NUMBER_RE.finditer(t)]
    return [q for q in qs if re.search(r"\d", q) and not YEAR_RE.fullmatch(q.strip())]


def tag(sentence: str) -> tuple[float, str, list[str]]:
    """Return (score 0..1, kind, quantities) for one sentence."""
    t = sentence.translate(_DEV_DIGITS)
    qs = quantities(t)
    has_date = bool(DATE_RE.search(t) or YEAR_RE.search(t))
    has_attr = bool(ATTRIBUTION_RE.search(t))
    has_entity = bool(re.search(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b", sentence))
    score = 0.0
    kind = "other"
    if qs:
        score += 0.45
        kind = "numeric"
    if has_date:
        score += 0.2
        kind = "date" if kind == "other" else kind
    if has_attr:
        score += 0.3
        kind = "attribution" if kind == "other" else kind
    if has_entity:
        score += 0.1
        kind = "entity" if kind == "other" else kind
    if OPINION_RE.search(t) or sentence.rstrip().endswith("?"):
        score -= 0.4
    return max(0.0, min(1.0, score)), kind, qs


JUNK_RE = re.compile(r"^[\W\d_]*(date|dated|time|source|follow us|subscribe|share)?[\W\d_:/.-]*$|^@\w+$", re.I)


def is_junk(sentence: str, min_words: int = 5) -> bool:
    """Fragments that are not claims: bare dates, handles, numbers, very short OCR pieces."""
    words = re.findall(r"\w+", sentence)
    return len(words) < min_words or bool(JUNK_RE.match(sentence.strip()))


def candidates(text: str, source: str, min_score: float = 0.3) -> list[dict]:
    out = []
    for s in split_sentences(text):
        s = s.translate(_DEV_DIGITS)
        if is_junk(s):
            continue
        score, kind, qs = tag(s)
        if score >= min_score:
            out.append({"text": s, "kind": kind, "score": round(score, 2), "source": source, "quantities": qs})
    return out
