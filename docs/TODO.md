# Progress & TODO (last updated 9 Oct 2026)

## Done
- [x] Research → `docs/research.md` (all 7 topics, live-tested platforms/APIs)
- [x] Architecture draft → `docs/architecture.md`; decisions approved: Groq LLM, X via embed endpoint only,
      Reddit = planned (oEmbed title only), Instagram unsupported, FastAPI + SQLite
- [x] venv + deps (`requirements.txt`; Deno + ffmpeg come from pip, no system installs)
- [x] Module 1 `ingest/`: router, yt-dlp/X/Reddit/article/image download, faster-whisper STT, EasyOCR (hi+en)
      — verified on YouTube + X
- [x] Module 2 `claims/`: rule tagger (EN+HI), LLM extractor (Groq) with rule fallback, sources (Google Fact Check
      API, Alt News/Factly/Vishvas search feeds, PIB + fact-checker RSS, GDELT, Tavily), e5 re-ranker,
      verifier (LLM w/ citations, NLI fallback, numeric check, "no evidence → unverifiable" enforced in code)
- [x] Module 3 `propagation/`: YouTube + GDELT search, MinHash + embedding matching, 6-h burst z-score,
      CooRTweet-style coordination clusters, cautious wording
- [x] Module 4 `app/`: FastAPI, result page (verdicts, evidence links, timeline charts), history, upload fallback, JSON API
- [x] 34 offline tests passing (`pytest`)
- [x] Fixes from smoke runs: sentence-transformers 6.x incompatibility (switched to plain transformers),
      GDELT 429 backoff + cache, OCR capped at 10 frames (was ~10 min per clip), stale jobs marked on restart

- [x] API keys set up (Groq, Google, Tavily) and verified live
- [x] Example run #1 with keys (DD News G20 clip `Pqr5VuY_zBc`) → found and fixed: LLM treating media repetition as
      support (main claim was wrongly "supported"), circular evidence (the post itself), "G20" parsed as a number,
      propagation searching relative to today instead of the post's date. Re-run: main claim now "contradicted"
      citing PIB fact-check coverage.

- [x] Speed: 722 s -> 182 s per 42 s clip (Whisper threads, STT||OCR, embedding cache, parallel claims)
- [x] Evaluations run -> docs/evaluation.md (QuanTemp NLI n=300, LLM n=150; synthetic propagation, window tuned
      60 -> 10 min and validated on a held-out seed)

- [x] Write-ups: docs/OVERVIEW.md (professor brief), final docs/architecture.md (6 Mermaid diagrams, module specs,
      API, ADRs), docs/limitations.md (limitations, ethics, future scope incl. account-history analysis), README

## Left
1. Forced-choice QuanTemp LLM run (same 150 claims) for like-for-like comparison with the paper (needs Groq quota).
2. Claim `context` attribution is sometimes wrong (says "PIB screenshot" for numbers that came from the tweet).
3. Re-test: Hindi-speech clip, X post, news article, upload; check GDELT news results with date windows.
4. Tune `MIN_RELEVANCE` (claims/retrieve.py) and similarity thresholds on real runs.
5. Optional extra evaluation: AVeriTeC dev subset; CheckThat! check-worthiness for the claim extractor.
6. 4–5 documented real example runs (YouTube Hindi, X post, news article, upload, unsupported Instagram).
8. Optional polish: UI review, a progress bar per stage, Dockerfile.
