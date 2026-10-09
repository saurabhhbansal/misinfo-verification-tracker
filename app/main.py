"""FastAPI web app. Run:  uvicorn app.main:app --reload  then open http://127.0.0.1:8000"""
from __future__ import annotations

import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db, pipeline, views
from common import config, llm
from ingest import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
BASE = Path(__file__).parent
app = FastAPI(title="Misinformation Verification & Propagation Tracker", version="0.1")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
views.register_filters(templates.env)
# one job at a time: STT/OCR models are CPU-heavy
executor = ThreadPoolExecutor(max_workers=1)
UPLOAD_EXT = {".mp4", ".mov", ".webm", ".mkv", ".mp3", ".m4a", ".wav", ".ogg", ".jpg", ".jpeg", ".png", ".webp"}
db.init()


def services() -> dict:
    return {"LLM (Groq)": llm.available(), "Google Fact Check + YouTube": bool(config.GOOGLE_API_KEY),
            "Web search (Tavily)": bool(config.TAVILY_API_KEY), "GDELT news": True, "Indian fact-checker RSS": True}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, error: str | None = None):
    return templates.TemplateResponse(request, "index.html", {
        "platforms": router.PLATFORMS, "services": services(), "recent": db.recent(8), "error": error})


@app.post("/check")
def submit(url: str = Form(...)):
    url = url.strip()
    try:
        info = router.detect(url)
    except ValueError as e:
        return RedirectResponse(f"/?error={quote(str(e))}", status_code=303)
    cid = db.create(url, info.name)
    if info.support == "unsupported":
        db.update(cid, status="error", stage="Unsupported platform", error=info.reason, finished_at=db.now())
    else:
        executor.submit(pipeline.run, cid, url)
    return RedirectResponse(f"/check/{cid}", status_code=303)


@app.post("/upload")
async def upload(file: UploadFile = File(...), caption: str = Form("")):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in UPLOAD_EXT:
        return RedirectResponse(f"/?error={quote('Unsupported file type ' + ext)}", status_code=303)
    cid = db.create(f"upload://{file.filename}", "upload")
    dest_dir = config.MEDIA_DIR / cid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"upload{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    executor.submit(pipeline.run, cid, None, (dest, file.filename, caption))
    return RedirectResponse(f"/check/{cid}", status_code=303)


@app.get("/check/{cid}", response_class=HTMLResponse)
def result(request: Request, cid: str):
    check = db.get(cid)
    if not check:
        raise HTTPException(404, "Check not found")
    return templates.TemplateResponse(request, "result.html", {"c": check, "summary": views.summary(check)})


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    return templates.TemplateResponse(request, "history.html", {"recent": db.recent(100)})


@app.get("/api/checks/{cid}")
def api_check(cid: str):
    check = db.get(cid)
    if not check:
        raise HTTPException(404, "Check not found")
    return JSONResponse(check)


@app.get("/api/health")
def health():
    return services()
