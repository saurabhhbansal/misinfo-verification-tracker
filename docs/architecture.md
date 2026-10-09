# Architecture (PROPOSED — awaiting team approval)

Based on findings in [research.md](research.md). Status: draft, 9 Oct 2026.

## 1. High-level diagram

```mermaid
flowchart LR
    U[User pastes link<br/>or uploads file] --> W[FastAPI web app<br/>module 4]
    W -->|create job| DB[(SQLite<br/>checks, claims,<br/>evidence, posts)]
    W --> P[Pipeline orchestrator]

    subgraph M1[Module 1 · ingest]
        R[URL router<br/>platform detection] --> D[Downloader<br/>yt-dlp · gallery-dl ·<br/>X embed · trafilatura]
        D --> X[Extractor<br/>faster-whisper STT ·<br/>EasyOCR frames/images ·<br/>caption text]
    end

    subgraph M2[Module 2 · claims]
        CE[Claim extractor<br/>rules + LLM] --> QG[Query generator]
        QG --> EV[Evidence retriever<br/>Fact Check API · Indian FC RSS ·<br/>PIB RSS · GDELT · Tavily]
        EV --> RR[Re-ranker<br/>multilingual embeddings]
        RR --> VF[Verifier<br/>LLM w/ citations · NLI fallback ·<br/>numeric check]
    end

    subgraph M3[Module 3 · propagation]
        PS[Similar-post search<br/>YouTube API · GDELT ·<br/>X/Reddit if approved] --> SIM[Near-duplicate matching<br/>MinHash + embeddings]
        SIM --> BU[Burst + coordination<br/>time buckets · CooRTweet-style]
    end

    P --> M1 --> M2
    M1 --> M3
    M2 --> DB
    M3 --> DB
    DB --> RES[Result page<br/>claims · verdicts · evidence links ·<br/>propagation timeline]
```

## 2. Data flow (one check)

1. **Input** — URL (or uploaded file). Router identifies platform; unsupported platforms (Instagram) get a clear
   message + "upload the file instead" option.
2. **Download** to `data/media/<check_id>/` — video/audio/images + metadata (author, timestamp, caption, counts).
3. **Extract** → `ContentBundle { caption, transcript (lang, segments), ocr_lines, metadata }`.
4. **Claims** → list of `Claim { text_original, text_en, type: numeric|date|attribution|entity|other, source: caption|speech|ocr, spans }`.
5. **Evidence** per claim → `Evidence { url, source_type: factcheck|govt|news|web, title, snippet, published, score }`.
6. **Verdict** per claim → `{ label: supported|contradicted|conflicting|unverifiable, rationale, cited_evidence_ids, confidence }`.
   Code-level guard: label ≠ unverifiable requires ≥1 cited evidence URL.
7. **Propagation** → `{ matches: [Post], timeline buckets, burst_score, distinct_authors, coordination_clusters, flag }`.
8. Saved to SQLite; result page renders; JSON also available at `/api/checks/{id}`.

Jobs run in a background thread (FastAPI `BackgroundTasks`); the result page polls a status endpoint, showing
progress per stage.

## 3. Folder layout (one owner per module)

```
app/                       # module 4 — FastAPI app, templates, static, orchestrator, db
  main.py  pipeline.py  db.py  templates/  static/
ingest/                    # module 1 — router, downloaders, STT, OCR
claims/                    # module 2 — extraction, retrieval, verification
propagation/               # module 3 — search, similarity, burst/coordination
common/                    # shared dataclasses, config (.env), LLM client wrapper
eval/                      # evaluation scripts + results
tests/                     # pytest per module (network calls mocked)
docs/
```

## 4. Tech choices

| Concern | Choice | Why |
|---|---|---|
| Web | FastAPI + Jinja2 + vanilla JS | async-friendly, auto OpenAPI docs, simple |
| DB | SQLite (stdlib `sqlite3`) | zero setup |
| Download | yt-dlp[default] + Deno + ffmpeg; gallery-dl; trafilatura | see research §1 |
| STT | faster-whisper `small` int8 (CPU) | Hindi+English, runs on laptop |
| OCR | EasyOCR `['hi','en']` | pip-only install on Windows |
| Embeddings | `intfloat/multilingual-e5-base` (or `-small` for speed) | Hindi/English, MIT |
| NLI fallback | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | multilingual, no API |
| LLM | pending decision D1 (recommend Groq free tier) | |
| Near-dup | datasketch MinHash + embeddings | |

## 5. Open decisions
See research.md §8 (D1 LLM, D2 X content, D3 Reddit app, D4 framework).
