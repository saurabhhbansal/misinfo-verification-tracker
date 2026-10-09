# Limitations, Ethics and Future Scope

**Last updated:** 9 Oct 2026 · Related: [OVERVIEW](OVERVIEW.md) · [evaluation](evaluation.md)

## 1. Limitations

### 1.1 Platform access (largest constraint)
| Platform | What we cannot do | Reason (verified 9 Oct 2026) |
|---|---|---|
| X / Twitter | search for similar posts, read repost cascades | official API is pay-per-use only for new developers ($0.005 per post read) |
| Reddit | read post bodies or comments, search | anonymous access returns HTTP 403; API needs manual approval |
| Instagram | download anything | requires login (outside project rules) |
| Facebook | search, private / non-video posts | no public search API since CrowdTangle shut down (Aug 2024) |
| X embed endpoint | guaranteed availability | undocumented; may change without notice |

**Consequence:** propagation is measured on YouTube and news coverage only, and cannot see the platforms where most
Indian misinformation actually spreads (WhatsApp, X, Instagram).

### 1.2 Claim verification
- **High abstention.** About 74% of QuanTemp claims come out `unverifiable`. This is safe but less useful, and is
  partly caused by weak evidence in the benchmark setting.
- **"Conflicting / missing context" class is weak:** 0 correct of 36 in the LLM run.
- **Evidence coverage depends on search results.** If no indexed source has covered a claim, the answer is
  `unverifiable` even when the claim is false.
- **Recency bias of feeds:** RSS feeds expose only recent items. Older fact-checks are found only through search
  (Fact Check API, Tavily).
- **LLM limits:** free-tier token quotas (≈150–200 claims per day for evaluation); the model may still misread
  evidence. Every verdict therefore shows its sources for the user to check.
- **Claim context is sometimes misattributed** (who said it). This has not changed a verdict in testing.

### 1.3 Speech and OCR
- Whisper `small` transcribes Hindi with spelling errors. Code-mixed Hinglish is weaker still.
- OCR misreads stylised fonts and moving tickers (e.g. "G२O"). Only 10 frames per video are read.
- Videos longer than 10 minutes are rejected to keep runtime reasonable.

### 1.4 Propagation
- **Organic vs coordinated:** fast organic viral sharing can trigger the coordination flag (15 false alarms per 100
  organic scenarios on the held-out synthetic set).
- **Evaluated on synthetic data only:** no free labelled dataset with post-level timestamps exists today.
- Time buckets and thresholds are fixed, not adaptive per topic.

### 1.5 Engineering
- Single process, one job at a time; not designed for many simultaneous users.
- CPU-only: about 3 minutes per short video.

## 2. Ethics and responsible use
- Only public content is accessed; no logins, cookies or bypassing of access controls.
- Verdicts are presented as automated assessments with evidence, not final judgements. Users are told to open the
  sources.
- Propagation wording avoids labelling people as bots or bad actors.
- Benchmark datasets (QuanTemp, AVeriTeC) are CC BY-NC 4.0: academic, non-commercial use, with credit.

## 3. Future scope

| # | Item | Value | Effort / dependency |
|---|---|---|---|
| F1 | **Original-poster account-history analysis**: account age, posting frequency, past fact-checked posts, follower/following patterns | separates habitual misinformation sources from one-off sharers; strengthens the coordination signal | needs platform APIs with user timelines (X paid, Reddit approval); deferred by team decision |
| F2 | X and Reddit propagation search | covers the main spreading platforms | paid X API credits; Reddit app approval |
| F3 | Reverse image / video search (perceptual hashes: PDQ / vPDQ) | catches recycled old media, a very common Indian misinformation pattern | open-source hashing; needs a searchable index |
| F4 | Better Hindi ASR (AI4Bharat IndicConformer) and OCR (PaddleOCR Devanagari) | fewer transcription and OCR errors | heavier install |
| F5 | Forced-choice benchmark run and claim-detection evaluation (CheckThat!) | like-for-like comparison with literature | Groq quota only |
| F6 | Fine-tune a small verifier on QuanTemp train | fine-tuned NLI models in the QuanTemp paper reach 52–58 macro-F1, vs 47 for few-shot gpt-3.5 | GPU hours |
| F7 | Use structured government data (data.gov.in API) for statistical claims | direct verification of numbers | per-dataset mapping |
| F8 | Job queue and multi-user deployment (Docker, Redis) | real-world use | standard engineering |
| F9 | WhatsApp tip-line integration (forwarded media → check) | where Indian misinformation actually spreads | WhatsApp Business API terms |
