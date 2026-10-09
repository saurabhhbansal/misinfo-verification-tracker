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

## Left
1. **Get free API keys** (one team member creates accounts) and put them in `.env`:
   `GROQ_API_KEY`, `GOOGLE_API_KEY` (enable Fact Check Tools API + YouTube Data API v3), `TAVILY_API_KEY`.
   Without them the app still runs, but evidence is thin and most verdicts come out "unverifiable".
2. Finish the example run in progress (DD News clip `Pqr5VuY_zBc`), check timing after the OCR fix.
3. Re-test with keys: LLM claim extraction (Hindi clip), Fact Check API, YouTube propagation search.
4. Tune `MIN_RELEVANCE` (claims/retrieve.py) and similarity thresholds on real runs.
5. Evaluation:
   - `python -m eval.quantemp_eval --method nli --n 300` (data already in `data/eval/quantemp/`)
   - same with `--method llm` once Groq key is set
   - `python -m eval.propagation_eval --n 200` (synthetic coordination)
   - optional: AVeriTeC dev subset; CheckThat! check-worthiness for the claim extractor
6. 4–5 documented real example runs (YouTube Hindi, X post, news article, upload, unsupported Instagram).
7. README (setup, keys, run, module owners), `.env.example`, `docs/architecture.md` → final version,
   limitations + future scope (incl. original-poster account-history analysis, Reddit/X search, IndicConformer,
   PaddleOCR, image reverse search).
8. Optional polish: UI review, a progress bar per stage, Dockerfile.
