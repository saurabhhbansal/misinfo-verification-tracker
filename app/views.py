"""Presentation helpers (Jinja filters, summary numbers, timeline chart geometry)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

LABEL_TEXT = {"supported": "Supported", "contradicted": "Contradicted", "conflicting": "Conflicting / missing context",
              "unverifiable": "Unverifiable"}
LEVEL_TEXT = {"high": "Possible coordinated spreading", "elevated": "Unusual burst", "moderate": "Some clustering",
              "low": "No unusual spread", "insufficient": "Not enough data"}


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except ValueError:
        return url


def fmt_date(s: str | None) -> str:
    if not s:
        return ""
    for parse in (lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
                  lambda x: datetime.strptime(x, "%a %b %d %H:%M:%S %z %Y"),
                  lambda x: datetime.strptime(x, "%a, %d %b %Y %H:%M:%S %z")):
        try:
            return parse(s).strftime("%d %b %Y")
        except (ValueError, TypeError):
            continue
    return s[:16]


def register_filters(env):
    env.filters["domain"] = domain
    env.filters["date"] = fmt_date
    env.filters["label_text"] = lambda l: LABEL_TEXT.get(l, l)
    env.filters["level_text"] = lambda l: LEVEL_TEXT.get(l, l or "")
    env.globals["bars"] = bars


def summary(check: dict) -> dict:
    claims = check.get("claims") or []
    return {"counts": Counter(c["verdict"]["label"] for c in claims), "n": len(claims)}


def bars(series: list[dict], key: str = "count", width: int = 640, height: int = 120) -> dict:
    """Geometry for a simple SVG bar chart rendered in the template (no JS chart library)."""
    vals = [float(p.get(key) or 0) for p in series]
    if not vals:
        return {"bars": [], "max": 0, "width": width, "height": height}
    vmax = max(vals) or 1
    n = len(vals)
    bw = width / n
    out = []
    for i, (p, v) in enumerate(zip(series, vals)):
        h = (v / vmax) * (height - 18)
        label = p.get("start") or p.get("date") or ""
        out.append({"x": round(i * bw + bw * 0.1, 1), "w": round(max(bw * 0.8, 1), 1), "y": round(height - h, 1),
                    "h": round(h, 1), "v": int(v) if v.is_integer() else round(v, 1), "label": fmt_date(_gd(label))})
    return {"bars": out, "max": int(vmax), "width": width, "height": height,
            "first": out[0]["label"], "last": out[-1]["label"]}


def _gd(s: str) -> str:
    # GDELT timeline dates look like 20261001T000000Z
    if len(s) == 16 and s[8] == "T":
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:00+00:00"
    return s
