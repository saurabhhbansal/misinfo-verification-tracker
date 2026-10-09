"""Central configuration. Values come from environment variables / a local .env file.

Every external service is optional: when a key is missing the pipeline skips that
source (and says so in the result) instead of crashing.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
MEDIA_DIR = DATA_DIR / "media"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "checks.db"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# --- API keys (all free tiers; see README) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")  # Fact Check Tools + YouTube Data v3
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# --- models ---
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # tiny | base | small | medium | large-v3
EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
NLI_MODEL = os.getenv("NLI_MODEL", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")

# --- limits (keep free-tier usage low) ---
MAX_MEDIA_SECONDS = int(os.getenv("MAX_MEDIA_SECONDS", "600"))
MAX_CLAIMS = int(os.getenv("MAX_CLAIMS", "6"))
OCR_EVERY_SECONDS = float(os.getenv("OCR_EVERY_SECONDS", "2"))
OCR_MAX_FRAMES = int(os.getenv("OCR_MAX_FRAMES", "10"))  # ~5 s CPU per frame

HTTP_HEADERS = {"User-Agent": "MisinfoTracker/0.1 (academic capstone; PEC Chandigarh)"}
