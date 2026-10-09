# Evaluation (9 Oct 2026)

All numbers below come from the scripts in `eval/`; raw outputs and per-claim predictions are in `eval/results/`.
Nothing was trained. Every model is used zero-shot.

## 1. Claim verification on QuanTemp (module 2)

**Dataset.** QuanTemp test split (Venktesh et al., SIGIR 2024, [arXiv 2403.17169](https://arxiv.org/abs/2403.17169),
CC BY-NC 4.0). These are real numerical claims from 45 fact-checking organisations, labelled True / False / Conflicting.
We used a random sample (seed 42) of 300 claims for the offline model and the first 150 of the same sample for the LLM
(limited by the Groq free-tier daily token quota; one verdict uses about 850 tokens).

**Setting.** We used the authors' released BM25 top-100 evidence snippets, re-ranked with our multilingual-e5 embedder,
and passed the top 5 to our verifier, exactly as it runs in the app. QuanTemp has no "not enough evidence" label, so our
`unverifiable` answers are scored two ways:
- *strict*: `unverifiable` counts as wrong;
- *answered*: only the claims where the system committed to a verdict, plus *coverage* = the share answered.

| Verifier (same 150 claims) | Coverage | Answered accuracy | Answered macro-F1 | Strict accuracy | Strict macro-F1 |
|---|---|---|---|---|---|
| Majority class ("False") | 100% | 56.0% | 0.239 | 56.0% | 0.239 |
| Offline NLI (mDeBERTa-v3 XNLI) | 22.7% | 41.2% | 0.362 | 9.3% | 0.150 |
| **LLM (Groq gpt-oss-120b)** | 26.0% | **56.4%** | **0.422** | 14.7% | 0.205 |

On all 300 claims the NLI model's figures were: coverage 27.0%, answered accuracy 49.4%, answered macro-F1 0.405.
In the LLM run, 12 of 150 claims fell back to NLI after Groq rate-limit errors (`verdict_methods` in the JSON).

**Published reference points** (QuanTemp paper, Tables 7–8, forced 3-way choice, no abstention):
- NLI models *fine-tuned on QuanTemp*: 52–58 macro-F1. Gold-evidence upper bound: 62.9.
- Few-shot LLMs: GPT-4 36.5, gpt-3.5-turbo 47.0 macro-F1.

**What this shows**
1. The system abstains a lot (about 74% `unverifiable`). This is by design: the project rule is "no verdict without
   evidence", and the verifier prompt says that articles which merely repeat a claim do not support it. QuanTemp's
   snippets come from general web pages (fact-check sites are removed to avoid leakage), so they rarely settle a claim
   on their own.
2. When it does answer, the LLM's macro-F1 (0.42) is in the range of the published few-shot LLM results. It is not
   directly comparable, because those were forced to answer every claim.
3. The LLM beats the offline NLI fallback on the same claims: +15 points answered accuracy, +0.06 answered macro-F1.
4. The "Conflicting" class is almost never predicted correctly (0 correct of 36 in the LLM run). This is the hardest
   class in the paper too (F1 0.33–0.49 even for fine-tuned models).

**Planned follow-up:** a forced-choice run (no `unverifiable` option) on the same 150 claims, for a like-for-like
comparison with the paper. It needs another day of Groq quota.

## 2. Propagation / coordination detection (module 3), synthetic

Why synthetic: labelled datasets with post-level timestamps (e.g. FakeNewsNet) need tweet hydration via the
now-paid X API (research.md §6–7).

Each scenario contains 10–30 unrelated background posts plus one of:
- *spread*: an organic share pattern over days;
- *wave*: an organic viral wave of 15–40 accounts over hours;
- *self*: one account spamming.

Positive scenarios add 3–10 accounts posting lightly edited copies within 2–50 minutes. Messages come from real
QuanTemp claims. The detection code is exactly the app's matching + burst + coordination logic, without the network
search.

| Coordination window | Seed | Precision | Recall | F1 | False alarms (of 100 negatives) |
|---|---|---|---|---|---|
| 60 min (original) | 7 (tuning) | 0.774 | 0.96 | 0.857 | 28, all organic waves |
| 10 min | 7 (tuning) | 0.901 | 0.91 | 0.905 | 10 |
| 2 min | 7 (tuning) | 1.000 | 0.58 | 0.734 | 0 |
| 60 min | **11 (held-out)** | 0.781 | 1.00 | 0.877 | 28 |
| **10 min (now default)** | **11 (held-out)** | **0.864** | **0.95** | **0.905** | 15 |

**Takeaways**
- Every false alarm was an organic viral wave. Timing alone cannot fully separate "many real people share quickly"
  from "a coordinated group". This is why the UI says "consistent with coordinated spreading (not proof)".
- These numbers measure the detection logic on synthetic data, not real-world accuracy. Real-world recall is also
  limited by which platforms can be searched (YouTube + news only, see README).

## 3. Example run

**DD News, PIB fact-check of the G20 "300% overspending" claim** (YouTube `Pqr5VuY_zBc`, 42 s, Hindi + English):

| Claim (extracted from OCR of the tweet screenshot) | Verdict | Evidence |
|---|---|---|
| Modi Govt spent 300% more on G20 than the funds allocated | contradicted | Deccan Herald and India Today reports of the PIB fact-check |
| ₹990 Cr was allocated for the G20 summit in the Union Budget | supported | Indian Express |
| Govt actually spent over ₹4,100 Cr | unverifiable (sources only repeat the figure) | — |

- Propagation: no near-duplicate reposts on YouTube or news in the window around the post. The tweet spread on X, which
  we cannot search.
- Total time: 182 s on a CPU laptop (download 4 s, speech-to-text + OCR 75 s, claims 38 s, propagation 66 s).
  It was 722 s before the speed fixes.
- What the iterations fixed: the first run with keys marked the main claim *supported*, because media articles repeating
  the allegation were treated as confirmation. That is now prevented by the verifier prompt rules and a regression test.

More example runs (Hindi speech, X post, news article, upload, unsupported Instagram) are still to do; see TODO.md.
