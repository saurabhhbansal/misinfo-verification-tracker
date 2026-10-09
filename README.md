# Link-Based Misinformation Verification & Propagation Tracker

Final-year capstone (B.E. CSE Data Science, PEC Chandigarh). Paste a link to a public social-media post; the system
downloads it, transcribes speech (Hindi/English), reads on-screen text, extracts checkable claims, verifies each one
against fact-checkers, government releases and news **with evidence links**, and looks for signs of coordinated
spreading.

> Status: MVP in progress — see [docs/TODO.md](docs/TODO.md). Research: [docs/research.md](docs/research.md).
> Architecture: [docs/architecture.md](docs/architecture.md).

## Platforms
| Platform | Status |
|---|---|
| YouTube | supported |
| X / Twitter | supported (post text + media; no similar-post search — X API is paid) |
| Facebook | public videos only |
| Reddit | partial (title/author only — API needs approval) |
| Instagram | unsupported (needs login) → use **Upload a file** |
| News / other sites | supported |

## Setup (Windows, Python 3.11, no GPU needed)
```bash
python -m venv .venv
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements.txt
```
Deno (needed by yt-dlp for YouTube) and ffmpeg come from pip — no system installs.
First run downloads models (~1.5 GB: Whisper small, EasyOCR, multilingual-e5, mDeBERTa NLI).

## API keys (all free) — each person keeps their own `.env`
Create a file named `.env` in the project root (it is git-ignored — **never commit it**):
```
GROQ_API_KEY=
GOOGLE_API_KEY=
TAVILY_API_KEY=
```
| Key | Used for | Get it |
|---|---|---|
| `GROQ_API_KEY` | LLM claim extraction + verdicts | https://console.groq.com → API Keys |
| `GOOGLE_API_KEY` | Google Fact Check Tools API + YouTube Data API v3 (enable both on one project) | https://console.cloud.google.com → APIs & Services |
| `TAVILY_API_KEY` | web + govt-site search (1,000/month) | https://app.tavily.com |

Any missing key just disables that source; the app still runs (verdicts fall back to an offline NLI model and are
more often "unverifiable").

## Run
```bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Open http://127.0.0.1:8000 — API docs at `/docs`.

## Tests & evaluation
```bash
.venv\Scripts\python -m pytest
.venv\Scripts\python -m eval.quantemp_eval --method nli --n 300
.venv\Scripts\python -m eval.propagation_eval --n 200
```
QuanTemp data goes in `data/eval/quantemp/` (download steps in docs/TODO.md).

## Modules (one owner each)
| Folder | Module |
|---|---|
| `ingest/` | 1 · link input, download, speech-to-text, OCR |
| `claims/` | 2 · claim extraction + verification against news / fact-check / govt sources |
| `propagation/` | 3 · similar posts, burst + coordination detection |
| `app/` | 4 · website, database, pipeline integration |
| `common/` | shared config, data models, LLM / embedding / GDELT clients |
