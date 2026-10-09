"""Synthetic evaluation of module 3 (burst + coordination flags).

Why synthetic: labelled coordinated-sharing datasets with post-level timestamps (e.g. FakeNewsNet) need tweet
hydration through the now-paid X API, so they cannot be rebuilt for free (research.md §6-7).

Each scenario = one "checked post" + candidate posts found by search:
  * background: unrelated posts (other QuanTemp claims) at random times over 30 days
  * organic sharing (negatives): the same message shared by different accounts spread over days,
    sometimes a large organic wave (many accounts over 1-3 days), or one account repeating itself
  * coordinated (positives): k distinct accounts post near-identical copies (light edits, hashtags)
    within a short window (2-50 minutes), on top of background + organic noise
Run:  python -m eval.propagation_eval --n 200
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from common.models import Post  # noqa: E402
from propagation import burst, similarity  # noqa: E402

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
TAGS = ["#breaking", "#India", "#truth", "#share", "#viral", "🔥", "‼️", "#news"]


def perturb(text: str, rnd: random.Random) -> str:
    """Light edits typical of copy-paste campaigns."""
    t = text
    if rnd.random() < 0.5:
        t = t.upper() if rnd.random() < 0.2 else t.lower()
    if rnd.random() < 0.5:
        t = t.replace(",", "").replace(".", "!")
    if rnd.random() < 0.7:
        t = t + " " + " ".join(rnd.sample(TAGS, rnd.randint(1, 3)))
    if rnd.random() < 0.3:
        t = rnd.choice(["Must read: ", "Shocking: ", "BREAKING - ", ""]) + t
    return t


def mk(i, author, minutes, text):
    return Post(platform="x", post_id=str(i), author=author,
                published=(T0 + timedelta(minutes=minutes)).isoformat(), text=text, url=f"https://x.com/{author}/{i}")


def scenario(message: str, pool: list[str], positive: bool, rnd: random.Random) -> list[Post]:
    posts, n = [], 0
    for _ in range(rnd.randint(10, 30)):                                # unrelated background
        posts.append(mk(n, f"bg{n}", rnd.uniform(0, 43200), rnd.choice(pool)))
        n += 1
    kind = rnd.choice(["spread", "wave", "self"])
    if kind == "spread":                                                # organic: same message over days
        for _ in range(rnd.randint(3, 15)):
            posts.append(mk(n, f"org{n}", rnd.uniform(0, 43200), perturb(message, rnd)))
            n += 1
    elif kind == "wave":                                                # organic viral wave over 1-3 days
        start = rnd.uniform(0, 38000)
        for _ in range(rnd.randint(15, 40)):
            posts.append(mk(n, f"org{n}", start + rnd.expovariate(1 / rnd.uniform(240, 1440)), perturb(message, rnd)))
            n += 1
    else:                                                               # one account spamming itself
        start = rnd.uniform(0, 40000)
        for j in range(rnd.randint(4, 10)):
            posts.append(mk(n, "spammer", start + j * rnd.uniform(1, 5), perturb(message, rnd)))
            n += 1
    if positive:                                                        # coordinated cluster
        k, window = rnd.randint(3, 10), rnd.uniform(2, 50)
        start = rnd.uniform(0, 43000)
        for j in range(k):
            posts.append(mk(n, f"coord{j}", start + rnd.uniform(0, window), perturb(message, rnd)))
            n += 1
    return posts


def detect(message: str, posts: list[Post]) -> tuple[str, int]:
    """Same logic as propagation.report.analyse, minus the network search."""
    scores = similarity.score_candidates(message, [p.text for p in posts])
    matches = [p for p, (j, c) in zip(posts, scores) if similarity.is_match(j, c)]
    matches.sort(key=lambda p: p.published)
    stats = burst.burst_stats(burst.buckets(matches, hours=6))
    clusters = []
    if len(matches) >= 2:
        mh = [similarity.minhash(p.text) for p in matches]
        jac = np.array([[a.jaccard(b) for b in mh] for a in mh])
        clusters = burst.coordination(matches, jac, sim_threshold=0.8, time_window_s=3600)
    level, _ = burst.assess(stats, clusters, len(matches))
    return level, len(matches)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rnd = random.Random(args.seed)
    claims = [c["claim"].strip('"') for c in
              json.load(open(ROOT / "data/eval/quantemp/test_claims_quantemp.json", encoding="utf-8"))]
    rnd.shuffle(claims)
    pool, messages = claims[:500], claims[500:500 + args.n]
    gold, pred_high, pred_any, rows, t0 = [], [], [], [], time.time()
    for i, msg in enumerate(messages):
        positive = i % 2 == 0
        level, n_match = detect(msg, scenario(msg, pool, positive, rnd))
        gold.append(int(positive))
        pred_high.append(int(level == "high"))
        pred_any.append(int(level in ("high", "elevated")))
        rows.append({"positive": positive, "level": level, "matches": n_match})
    res = {"n": len(gold), "seed": args.seed}
    for name, p in (("coordination_flag(high)", pred_high), ("any_flag(high|elevated)", pred_any)):
        res[name] = {"precision": round(precision_score(gold, p, zero_division=0), 3),
                     "recall": round(recall_score(gold, p, zero_division=0), 3),
                     "f1": round(f1_score(gold, p, zero_division=0), 3),
                     "confusion[[tn,fp],[fn,tp]]": confusion_matrix(gold, p).tolist()}
    res["seconds"] = round(time.time() - t0, 1)
    out = ROOT / "eval" / "results"
    out.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out / f"propagation_synthetic_n{args.n}.json", "w"), indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
