"""Shared data structures passed between the four modules."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

VERDICT_LABELS = ("supported", "contradicted", "conflicting", "unverifiable")


@dataclass
class ContentBundle:
    """Everything module 1 extracted from a post."""
    url: str
    platform: str
    title: str = ""
    caption: str = ""
    author: str = ""
    published: Optional[str] = None  # ISO 8601
    transcript: str = ""
    transcript_lang: str = ""
    ocr_lines: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)  # views, likes, reposts where the platform exposes them
    media_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # warnings shown to the user

    def full_text(self) -> str:
        parts = [self.title, self.caption, self.transcript, "\n".join(self.ocr_lines)]
        return "\n".join(p for p in parts if p).strip()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Claim:
    text: str                 # as stated (original language)
    text_en: str = ""         # English normalisation used for search
    kind: str = "other"       # numeric | date | attribution | entity | other
    source: str = "caption"   # caption | speech | ocr | title
    quantities: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)  # short search queries (LLM-generated if available)

    def query_text(self) -> str:
        return self.text_en or self.text

    def search_queries(self) -> list[str]:
        qs = list(self.queries) + [self.query_text()]
        if self.text != self.query_text():
            qs.append(self.text)
        seen, out = set(), []
        for q in qs:
            q = q.strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                out.append(q)
        return out[:3]


@dataclass
class Evidence:
    url: str
    title: str
    snippet: str
    source_type: str          # factcheck | govt | news | web
    publisher: str = ""
    published: Optional[str] = None
    rating: str = ""          # textual rating, for fact-check sources
    score: float = 0.0        # relevance to the claim (0..1)


@dataclass
class Verdict:
    label: str                # one of VERDICT_LABELS
    rationale: str
    evidence: list[Evidence] = field(default_factory=list)  # ONLY the cited evidence
    confidence: float = 0.0
    method: str = ""          # llm | nli | factcheck-match | none
    numeric_note: str = ""

    def __post_init__(self):
        if self.label not in VERDICT_LABELS:
            raise ValueError(f"bad label {self.label}")
        # Core rule of the project: no evidence -> no verdict.
        if self.label != "unverifiable" and not self.evidence:
            self.label = "unverifiable"
            self.rationale = "No evidence could be cited. " + self.rationale


@dataclass
class Post:
    """A post found during propagation search."""
    platform: str
    post_id: str
    author: str
    published: str            # ISO 8601
    text: str
    url: str
    similarity: float = 0.0
    stats: dict = field(default_factory=dict)
