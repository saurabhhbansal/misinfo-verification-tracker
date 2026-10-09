"""Module 3 tests (offline)."""
from datetime import datetime, timedelta, timezone

import numpy as np

from common.models import Post
from propagation import burst, similarity

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def post(i, minutes, author, text="same viral message about 80 crore people"):
    return Post(platform="x", post_id=str(i), author=author, published=(T0 + timedelta(minutes=minutes)).isoformat(),
                text=text, url=f"https://x.com/{author}/status/{i}")


def test_jaccard_near_duplicate_vs_unrelated():
    a = "BREAKING: Govt gives free laptop to all students, apply now at link"
    b = "Breaking - govt gives FREE laptop to all students!! apply now at link #share"
    c = "Cricket match result: India beat Australia by six wickets in Perth"
    assert similarity.jaccard(a, b) > 0.5 > similarity.jaccard(a, c)


def test_buckets_fill_gaps():
    s = burst.buckets([post(1, 0, "a"), post(2, 60 * 13, "b")], hours=6)
    assert [b["count"] for b in s] == [1, 0, 1]


def test_burst_detects_spike():
    posts = [post(i, i * 60 * 12, f"u{i}") for i in range(10)]                    # 1 post / 12h background
    posts += [post(100 + i, 60 * 60 + i, f"spam{i}") for i in range(12)]          # 12 posts in 12 minutes
    st = burst.burst_stats(burst.buckets(posts, hours=6))
    assert st["peak"] >= 12 and st["z"] >= 3.5 and st["peak_authors"] >= 12


def test_coordination_needs_distinct_accounts_and_time_window():
    posts = [post(1, 0, "a"), post(2, 5, "b"), post(3, 9, "c"), post(4, 600, "d")]
    sim = np.ones((4, 4))
    groups = burst.coordination(posts, sim, sim_threshold=0.9, time_window_s=3600, min_accounts=3)
    assert len(groups) == 1 and groups[0]["accounts"] == ["a", "b", "c"]
    # same account repeating itself is not coordination
    solo = [post(i, i, "a") for i in range(5)]
    assert burst.coordination(solo, np.ones((5, 5))) == []


def test_assess_levels():
    assert burst.assess({}, [], 1)[0] == "insufficient"
    assert burst.assess({"z": 0.5}, [], 10)[0] == "low"
    assert burst.assess({"z": 5, "peak": 20, "peak_authors": 15}, [], 30)[0] == "elevated"
    assert burst.assess({"z": 0}, [{"accounts": ["a", "b", "c"], "span_minutes": 4}], 5)[0] == "high"


def test_embeddings_work_from_worker_threads():
    """Regression: grad mode is thread-local; encoding from a worker thread must not leave grad-tracked tensors."""
    from concurrent.futures import ThreadPoolExecutor
    from common import embed
    with ThreadPoolExecutor(2) as ex:
        a = ex.submit(embed.encode, ["first text in a thread"]).result()
    b = embed.similarity(["first text in a thread"], ["another passage"])  # main thread afterwards
    assert a.shape[0] == 1 and b.shape == (1, 1)
