"""Burst (unusually high posting frequency) and coordination detection over matched posts.

* Burst: posts per time bucket; robust z-score of the peak bucket vs. the median/MAD of all buckets.
* Coordination (CooRTweet-style, Righetti & Balluff 2025): link two DIFFERENT accounts when they post
  near-identical content within `time_window`; connected groups of >= `min_accounts` accounts are flagged.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np

from common.models import Post


def parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def buckets(posts: list[Post], hours: int = 6) -> list[dict]:
    """Time series with empty buckets filled: [{'start': iso, 'count': n, 'authors': k}]."""
    times = [(parse_ts(p.published), p.author) for p in posts]
    times = [(t, a) for t, a in times if t]
    if not times:
        return []
    width = timedelta(hours=hours)
    t0 = min(t for t, _ in times)
    t0 = t0.replace(minute=0, second=0, microsecond=0)
    n = int((max(t for t, _ in times) - t0) / width) + 1
    counts, authors = Counter(), defaultdict(set)
    for t, a in times:
        i = int((t - t0) / width)
        counts[i] += 1
        authors[i].add(a)
    return [{"start": (t0 + i * width).isoformat(), "count": counts[i], "authors": len(authors[i])} for i in range(n)]


def burst_stats(series: list[dict]) -> dict:
    if not series:
        return {"peak": 0, "peak_start": None, "median": 0, "z": 0.0, "peak_authors": 0}
    c = np.array([b["count"] for b in series], dtype=float)
    med = float(np.median(c))
    mad = float(np.median(np.abs(c - med))) or 0.5  # avoid divide-by-zero on sparse series
    i = int(c.argmax())
    z = 0.6745 * (c[i] - med) / mad
    return {"peak": int(c[i]), "peak_start": series[i]["start"], "median": med, "z": round(float(z), 2),
            "peak_authors": series[i]["authors"], "buckets": len(series)}


def coordination(posts: list[Post], sim_matrix: np.ndarray, sim_threshold: float = 0.9,
                 time_window_s: int = 3600, min_accounts: int = 3) -> list[dict]:
    """Groups of distinct accounts that posted near-identical content within `time_window_s` of each other.

    `sim_matrix[i][j]` = content similarity (0..1) between posts i and j.
    """
    n = len(posts)
    ts = [parse_ts(p.published) for p in posts]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edges = 0
    for i in range(n):
        for j in range(i + 1, n):
            if not ts[i] or not ts[j] or posts[i].author == posts[j].author:
                continue
            if abs((ts[i] - ts[j]).total_seconds()) <= time_window_s and sim_matrix[i][j] >= sim_threshold:
                parent[find(i)] = find(j)
                edges += 1
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    out = []
    for idx in groups.values():
        accounts = sorted({posts[i].author for i in idx})
        if len(accounts) >= min_accounts:
            times = sorted(ts[i] for i in idx if ts[i])
            out.append({"accounts": accounts, "posts": [posts[i].url for i in idx],
                        "first": times[0].isoformat(), "last": times[-1].isoformat(),
                        "span_minutes": round((times[-1] - times[0]).total_seconds() / 60, 1)})
    return sorted(out, key=lambda g: -len(g["accounts"]))


def assess(stats: dict, clusters: list[dict], n_matches: int) -> tuple[str, str]:
    """Return (level, explanation). Wording is deliberately cautious."""
    if n_matches < 3:
        return "insufficient", "Too few similar posts were found on searchable platforms to judge spreading patterns."
    if clusters:
        g = clusters[0]
        return "high", (f"{len(g['accounts'])} different accounts posted near-identical content within "
                        f"{g['span_minutes']} minutes. This pattern is consistent with coordinated spreading "
                        "(not proof of it).")
    if stats.get("z", 0) >= 3.5 and stats.get("peak_authors", 0) >= 5:
        return "elevated", (f"Posting spiked to {stats['peak']} posts by {stats['peak_authors']} accounts in one "
                            f"window (robust z = {stats['z']}), well above the usual rate.")
    if stats.get("z", 0) >= 2:
        return "moderate", f"Some clustering in time (robust z = {stats['z']}), but not unusual enough to flag."
    return "low", "Similar posts are spread out over time; no unusual burst detected."
