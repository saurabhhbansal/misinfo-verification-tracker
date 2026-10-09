"""Orchestrator: runs modules 1 → 2 → 3 for one check and stores each stage's output."""
from __future__ import annotations

import logging
import time
import traceback
from dataclasses import asdict
from pathlib import Path

from app import db
from claims import extract as claim_extract
from claims import retrieve, verify
from common import llm
from common.models import ContentBundle
from ingest import extract as ingest
from propagation import report as propagation

log = logging.getLogger(__name__)


def _stage(cid: str, text: str):
    log.info("[%s] %s", cid, text)
    db.update(cid, status="running", stage=text)


def run(cid: str, url: str | None = None, upload: tuple[Path, str, str] | None = None):
    t0 = time.time()
    timings = {}
    try:
        # ---- module 1: download + extraction
        _stage(cid, "Downloading content")
        if upload:
            bundle = ingest.from_upload(*upload)
        else:
            bundle = ingest.fetch(url, cid)
        timings["download"] = round(time.time() - t0, 1)

        _stage(cid, "Extracting text (speech-to-text, OCR)")
        t = time.time()
        bundle = ingest.extract_text(bundle)
        timings["extract"] = round(time.time() - t, 1)
        db.update(cid, platform=bundle.platform, content=bundle.to_dict())

        # ---- module 2: claims + verification
        _stage(cid, "Finding checkable claims")
        t = time.time()
        claims, method = claim_extract.extract_claims(bundle)
        results, sources_used = [], set()
        for i, claim in enumerate(claims, 1):
            _stage(cid, f"Verifying claim {i} of {len(claims)}")
            evidence, used = retrieve.find_evidence(claim, bundle.url)
            sources_used.update(used)
            verdict = verify.verify(claim, evidence)
            results.append({"claim": asdict(claim), "verdict": asdict(verdict),
                            "considered": [asdict(e) for e in evidence]})
            db.update(cid, claims=results)
        timings["claims"] = round(time.time() - t, 1)
        db.update(cid, claims=results)

        # ---- module 3: propagation
        _stage(cid, "Searching for similar posts (propagation)")
        t = time.time()
        prop = propagation.analyse(bundle, claims)
        timings["propagation"] = round(time.time() - t, 1)

        meta = {"claim_method": method, "verify_method": "llm" if llm.available() else "nli",
                "evidence_sources": sorted(sources_used), "timings_s": timings,
                "total_s": round(time.time() - t0, 1)}
        db.update(cid, propagation=prop, meta=meta, status="done", stage="Finished", finished_at=db.now())
    except Exception as e:
        log.error("check %s failed: %s", cid, traceback.format_exc())
        db.update(cid, status="error", stage="Failed", error=str(e) or e.__class__.__name__, finished_at=db.now())


def run_bundle_only(bundle: ContentBundle) -> dict:
    """Synchronous helper for scripts/tests: modules 2 + 3 on an already-extracted bundle."""
    claims, method = claim_extract.extract_claims(bundle)
    results = []
    for c in claims:
        ev, _ = retrieve.find_evidence(c, bundle.url)
        results.append({"claim": asdict(c), "verdict": asdict(verify.verify(c, ev))})
    return {"claims": results, "claim_method": method, "propagation": propagation.analyse(bundle, claims)}
