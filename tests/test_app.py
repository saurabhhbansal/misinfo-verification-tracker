"""Module 4 tests: web routes and DB (pipeline mocked)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from common import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from app import db, main
    db.init()
    monkeypatch.setattr(main.executor, "submit", lambda *a, **k: None)  # don't run the real pipeline
    return TestClient(main.app)


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200 and "Check link" in r.text


def test_submit_and_view(client):
    r = client.post("/check", data={"url": "https://www.youtube.com/watch?v=abc"}, follow_redirects=False)
    assert r.status_code == 303
    cid = r.headers["location"].split("/")[-1]
    page = client.get(f"/check/{cid}")
    assert page.status_code == 200 and "Waiting to start" in page.text
    assert client.get(f"/api/checks/{cid}").json()["status"] == "queued"


def test_instagram_marked_unsupported(client):
    r = client.post("/check", data={"url": "https://www.instagram.com/reel/x/"})
    assert "requires login" in r.text


def test_result_page_renders_full_check(client):
    from app import db
    cid = db.create("https://x.com/a/status/1", "x")
    db.update(cid, status="done", stage="Finished", content={"url": "u", "platform": "x", "title": "", "caption": "c",
              "author": "@a", "published": None, "transcript": "", "transcript_lang": "", "ocr_lines": [],
              "stats": {"like_count": 5}, "media_paths": [], "notes": []},
              claims=[{"claim": {"text": "80 crore", "text_en": "", "kind": "numeric", "source": "caption",
                                 "quantities": [], "queries": []},
                       "verdict": {"label": "contradicted", "rationale": "r", "confidence": 0.8, "method": "llm",
                                   "numeric_note": "", "evidence": [{"url": "https://f.in/1", "title": "FC",
                                   "snippet": "", "source_type": "factcheck", "publisher": "Factly",
                                   "published": None, "rating": "False", "score": 0.9}]},
                       "considered": []}],
              propagation={"query": "q", "level": "low", "explanation": "e", "sources_used": ["GDELT news"],
                           "sources_unavailable": [], "matches": [], "timeline": [{"start": "2026-10-01T00:00:00+00:00", "count": 2, "authors": 2}],
                           "news_timeline": [], "burst": {"peak": 2, "peak_authors": 2, "peak_start": "2026-10-01T00:00:00+00:00", "median": 2, "z": 0}, "clusters": []},
              meta={"claim_method": "llm", "verify_method": "llm", "evidence_sources": [], "total_s": 1})
    r = client.get(f"/check/{cid}")
    assert r.status_code == 200 and "https://f.in/1" in r.text and "Contradicted" in r.text
    assert "history" in client.get("/history").text.lower()
