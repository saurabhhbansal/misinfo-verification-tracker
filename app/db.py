"""SQLite storage for past checks (stdlib sqlite3; one row per check, stage outputs stored as JSON)."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from common import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id          TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    platform    TEXT,
    status      TEXT NOT NULL,          -- queued | running | done | error
    stage       TEXT,                   -- human-readable current stage
    created_at  TEXT NOT NULL,
    finished_at TEXT,
    content     TEXT,                   -- JSON ContentBundle
    claims      TEXT,                   -- JSON list of {claim, verdict, evidence}
    propagation TEXT,                   -- JSON propagation report
    meta        TEXT,                   -- JSON: methods used, sources used, timings
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_checks_created ON checks(created_at DESC);
"""
JSON_COLS = ("content", "claims", "propagation", "meta")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _lock, connect() as c:
        c.executescript(SCHEMA)
        # jobs run in-process, so anything unfinished when the server stopped will never finish
        c.execute("UPDATE checks SET status='error', stage='Interrupted', error='Server restarted during this check; "
                  "please submit it again.' WHERE status IN ('queued','running')")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create(url: str, platform: str) -> str:
    cid = uuid.uuid4().hex[:12]
    with _lock, connect() as c:
        c.execute("INSERT INTO checks (id, url, platform, status, stage, created_at) VALUES (?,?,?,?,?,?)",
                  (cid, url, platform, "queued", "Waiting to start", now()))
    return cid


def update(cid: str, **fields):
    for k in JSON_COLS:
        if k in fields and not isinstance(fields[k], str) and fields[k] is not None:
            fields[k] = json.dumps(fields[k], ensure_ascii=False, default=str)
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock, connect() as c:
        c.execute(f"UPDATE checks SET {cols} WHERE id=?", (*fields.values(), cid))


def get(cid: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM checks WHERE id=?", (cid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for k in JSON_COLS:
        d[k] = json.loads(d[k]) if d[k] else None
    return d


def recent(limit: int = 30) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT id, url, platform, status, created_at, claims, propagation FROM checks "
                         "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        claims = json.loads(d.pop("claims") or "[]")
        prop = json.loads(d.pop("propagation") or "{}")
        d["n_claims"] = len(claims)
        d["labels"] = [c["verdict"]["label"] for c in claims]
        d["spread_level"] = prop.get("level")
        out.append(d)
    return out
