# Link-Based Misinformation Verification & Propagation Tracker

Final-year capstone · B.E. CSE (Data Science) · PEC Chandigarh · 2026

Paste a link to a public social-media post. The system:
1. downloads it;
2. transcribes speech and reads on-screen text (Hindi + English);
3. extracts checkable claims (numbers, dates, names, "according to…");
4. checks each claim against fact-checkers, government sources and news, **always showing the evidence links**;
5. looks for signs of coordinated spreading.

**Start here → [docs/OVERVIEW.md](docs/OVERVIEW.md)** (5-minute project brief).

| Document | Contents |
|---|---|
| [OVERVIEW](docs/OVERVIEW.md) | problem, approach, architecture at a glance, results, limitations |
| [architecture](docs/architecture.md) | components, sequence, data model, module specs, API, design decisions |
| [research](docs/research.md) | survey of papers (2024–2026), tools and API access, all verified live |
| [evaluation](docs/evaluation.md) | QuanTemp claim-verification and synthetic propagation benchmarks |
| [limitations](docs/limitations.md) | limitations, ethics, future scope |
| [TODO](docs/TODO.md) | progress log and remaining work |

## Results snapshot
| | Result |
|---|---|
| Claim verification (QuanTemp, zero-shot LLM) | 56% accuracy / 0.42 macro-F1 on the claims it answers; abstains on ~74% (no verdict without evidence) |
| Coordination detection (synthetic, held-out) | precision 0.86 · recall 0.95 · F1 0.91 |
| Runtime, 42 s video, CPU laptop | 182 s end to end |
| Tests | 41 passing (`pytest`, network mocked) |

## Platform support
| Platform | Status |
|---|---|
| YouTube | ✅ supported |
| X / Twitter | ✅ post text + media (similar-post search on X needs the paid API → not used) |
| Facebook | ⚠️ public videos only |
| Reddit | ⚠️ title / author only (API needs approval) |
| Instagram | ❌ needs login → use **Upload a file** |
| News / other sites | ✅ supported |

## Setup (Windows, Python 3.11, no GPU needed)
```bash
python -m venv .venv
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements.txt
```
Deno (needed by yt-dlp for YouTube) and ffmpeg come from pip; no system installs are needed. The first run downloads
models (~1.5 GB: Whisper small, EasyOCR, multilingual-e5, mDeBERTa NLI).

## API keys (all free, all optional): each person keeps their own `.env`
Create a file named `.env` in the project root. It is git-ignored; **never commit it**.
```
GROQ_API_KEY=
GOOGLE_API_KEY=
TAVILY_API_KEY=
```
| Key | Used for | Get it |
|---|---|---|
| `GROQ_API_KEY` | LLM claim extraction + verdicts | https://console.groq.com → API Keys |
| `GOOGLE_API_KEY` | Fact Check Tools API + YouTube Data API v3 (enable both; create an API key under *Credentials*, choose "Public data") | https://console.cloud.google.com → APIs & Services |
| `TAVILY_API_KEY` | web + government-site search (1,000 per month) | https://app.tavily.com |

Without keys the app still runs. Verdicts then fall back to an offline NLI model and are more often "unverifiable".

## Run
```bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Open http://127.0.0.1:8000. API docs are at `/docs`.

## Tests and evaluation
```bash
.venv\Scripts\python -m pytest
.venv\Scripts\python -m eval.quantemp_eval --method nli --n 300
.venv\Scripts\python -m eval.quantemp_eval --method llm --n 150
.venv\Scripts\python -m eval.propagation_eval --n 200 --seed 11
```
QuanTemp data (CC BY-NC 4.0) is not in the repo. Download `data/raw_data/test_claims_quantemp.json` and
`data/bm25_scored_evidence/bm25_top_100_claimdecomp.json.zip` from https://github.com/factiverse/QuanTemp into
`data/eval/quantemp/`, renaming the zip to `bm25.zip`.

## Repository layout
| Folder | Module | Owner |
|---|---|---|
| `ingest/` | 1 · link input, download, speech-to-text, OCR | Member 1 |
| `claims/` | 2 · claim extraction, evidence retrieval, verification | Member 2 |
| `propagation/` | 3 · similar posts, burst + coordination detection | Member 3 |
| `app/` | 4 · website, database, pipeline orchestration | Member 4 |
| `common/` | shared data model, config, LLM / embedding / GDELT clients | all |
| `eval/` | benchmark scripts + `results/` | all |
| `tests/` | unit and regression tests | all |
| `docs/` | documentation | all |
