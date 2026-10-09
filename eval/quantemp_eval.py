"""Evaluate module 2's verifier on QuanTemp (numerical claims; Venktesh et al., SIGIR 2024, CC BY-NC 4.0).

Uses the authors' released BM25 top-100 evidence (so retrieval is fixed and comparable), our multilingual re-ranker
to pick the top-k passages, then our verifier (NLI fallback or LLM).

Label mapping: supported→True, contradicted→False, conflicting→Conflicting. QuanTemp has no "not enough info"
class, so `unverifiable` is reported two ways: counted as wrong (strict) and as abstention (coverage).

Data:  data/eval/quantemp/test_claims_quantemp.json  and  bm25.zip  (see README → Evaluation)
Run:   python -m eval.quantemp_eval --method nli --n 300
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from claims import retrieve, verify  # noqa: E402
from common import llm  # noqa: E402
from common.models import Claim, Evidence  # noqa: E402

DATA = ROOT / "data" / "eval" / "quantemp"
OUT = ROOT / "eval" / "results"
MAP = {"supported": "True", "contradicted": "False", "conflicting": "Conflicting", "unverifiable": "Unverifiable"}
LABELS = ["True", "False", "Conflicting"]


def load(n: int, seed: int):
    claims = json.load(open(DATA / "test_claims_quantemp.json", encoding="utf-8"))
    ev = json.loads(zipfile.ZipFile(DATA / "bm25.zip").read("bm25_top_100_claimdecomp.json"))
    assert len(claims) == len(ev)
    idx = list(range(len(claims)))
    random.Random(seed).shuffle(idx)
    return [(claims[i], ev[i]) for i in idx[:n]]


def evidence_for(item: dict, max_docs: int = 30) -> list[Evidence]:
    seen, out = set(), []
    for d in item["docs"]:
        k = d[:200]
        if k in seen:
            continue
        seen.add(k)
        out.append(Evidence(url=f"quantemp://doc/{len(out)}", title="", snippet=d[:900], source_type="web"))
        if len(out) >= max_docs:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["nli", "llm"], default="nli")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--top_k", type=int, default=5)
    args = ap.parse_args()
    if args.method == "llm" and not llm.available():
        sys.exit("GROQ_API_KEY not set")
    if args.method == "nli":
        verify.llm.available = lambda: False  # force the offline path

    rows, t0 = [], time.time()
    for i, (c, e) in enumerate(load(args.n, args.seed), 1):
        claim = Claim(text=c["claim"].strip('"'))
        ev = retrieve.rerank(claim, evidence_for(e), top_k=args.top_k, min_rel=0.0)
        v = verify.verify(claim, ev)
        if args.method == "llm":
            time.sleep(2.2)  # Groq free tier: 30 requests/min
        rows.append({"claim": claim.text, "gold": c["label"], "pred": MAP[v.label], "method": v.method,
                     "taxonomy": c.get("taxonomy_label"), "rationale": v.rationale[:300]})
        if i % 25 == 0:
            print(f"{i}/{args.n}  {time.time() - t0:.0f}s", flush=True)

    gold = [r["gold"] for r in rows]
    pred = [r["pred"] for r in rows]
    answered = [(g, p) for g, p in zip(gold, pred) if p != "Unverifiable"]
    majority = Counter(gold).most_common(1)[0][0]
    res = {
        "method": args.method, "n": len(rows), "seed": args.seed, "top_k": args.top_k,
        "strict_accuracy": round(accuracy_score(gold, pred), 4),
        "strict_macro_f1": round(f1_score(gold, pred, labels=LABELS, average="macro", zero_division=0), 4),
        "coverage": round(len(answered) / len(rows), 4),
        "answered_accuracy": round(accuracy_score(*zip(*answered)), 4) if answered else None,
        "answered_macro_f1": round(f1_score(*zip(*answered), labels=LABELS, average="macro", zero_division=0), 4)
        if answered else None,
        "majority_baseline": {"label": majority, "accuracy": round(gold.count(majority) / len(gold), 4),
                              "macro_f1": round(f1_score(gold, [majority] * len(gold), labels=LABELS,
                                                         average="macro", zero_division=0), 4)},
        "gold_distribution": dict(Counter(gold)), "pred_distribution": dict(Counter(pred)),
        "confusion_matrix": {"labels": LABELS + ["Unverifiable"],
                             "matrix": confusion_matrix(gold, pred, labels=LABELS + ["Unverifiable"]).tolist()},
        "report": classification_report(gold, pred, labels=LABELS, zero_division=0, output_dict=True),
        "verdict_methods": dict(Counter(r["method"] for r in rows)),  # 'nli'/'none' in an llm run = LLM call failed
        "seconds": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"quantemp_{args.method}_n{args.n}"
    json.dump(res, open(OUT / f"{stem}.json", "w"), indent=2)
    json.dump(rows, open(OUT / f"{stem}_predictions.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in res.items() if k != "report"}, indent=2))


if __name__ == "__main__":
    main()
