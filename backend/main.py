"""FastAPI app: one endpoint that runs the pipeline, plus the built frontend."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .data.parse_script import MAX_SCRIPT_CHARS, ScriptValidationError, format_scenes_as_script, parse_and_validate
from .data.scenes import SCENES
from .pipeline import run_pipeline

app = FastAPI(title="Clearance Compass")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# The pipeline is a single sequential run against a shared Gemini quota
# (see pipeline.py's _GEMINI_CONCURRENCY). A second concurrent run doesn't
# fail cleanly -- it doubles quota contention and both requests eventually
# time out. Reject a second call outright instead of racing them.
#
# This lock is process-local. It's a real single-flight guard only because
# Cloud Run is pinned to a single instance for this service (see README's
# "fresh-project quota" section) -- if maxScale is ever raised again before
# the Vertex AI quota is, this stops being globally exclusive.
_analysis_lock = asyncio.Lock()

# Cheap, honest abuse guards for a public, unauthenticated endpoint that
# spends real money per call (Parallel + Vertex AI). Not meant to replace a
# proper WAF/rate-limiter -- meant to bound worst-case cost for a hackathon
# demo without adding infra this project doesn't otherwise need.
_MAX_BODY_BYTES = MAX_SCRIPT_CHARS * 4  # generous slack over raw char cap for JSON overhead/UTF-8
_PER_IP_COOLDOWN_S = int(os.environ.get("ANALYZE_PER_IP_COOLDOWN_S", "60"))
_DAILY_ANALYSIS_CAP = int(os.environ.get("ANALYZE_DAILY_CAP", "50"))
_last_request_by_ip: dict[str, float] = {}
_daily_count = 0
_daily_count_date = datetime.now(timezone.utc).date()


def _check_daily_cap() -> None:
    """Raises if the daily cap is already reached. Doesn't count this call --
    call _consume_daily_cap() only once the request has actually passed
    validation and is about to spend money, so rejected/invalid requests
    don't burn down the budget."""
    global _daily_count, _daily_count_date
    today = datetime.now(timezone.utc).date()
    if today != _daily_count_date:
        _daily_count_date = today
        _daily_count = 0
    if _daily_count >= _DAILY_ANALYSIS_CAP:
        raise HTTPException(
            status_code=503,
            detail="Daily analysis limit reached for this demo deployment. Try again tomorrow.",
        )


def _consume_daily_cap() -> None:
    global _daily_count
    _daily_count += 1


def _check_per_ip_cooldown(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    last = _last_request_by_ip.get(ip)
    if last is not None and now - last < _PER_IP_COOLDOWN_S:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait a moment before starting another analysis (limit: 1 per {_PER_IP_COOLDOWN_S}s).",
        )
    _last_request_by_ip[ip] = now


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                {"detail": "Request body too large."}, status_code=413
            )
    return await call_next(request)


class AnalyzeRequest(BaseModel):
    script: str | None = None
    force_fresh: bool = False


@app.get("/api/demo-script")
async def demo_script() -> dict:
    return {"script": format_scenes_as_script(SCENES)}


@app.post("/api/analyze")
async def analyze(request: Request, body: AnalyzeRequest | None = Body(default=None)) -> JSONResponse:
    if _analysis_lock.locked():
        raise HTTPException(
            status_code=409,
            detail="An analysis is already running. Wait for it to finish before starting another.",
        )
    _check_per_ip_cooldown(request)
    _check_daily_cap()

    scenes = None
    warning = None
    if body is not None and body.script is not None:
        try:
            scenes, warning = parse_and_validate(body.script)
        except ScriptValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    force_fresh = body.force_fresh if body is not None else False
    _consume_daily_cap()
    async with _analysis_lock:
        graph = await run_pipeline(scenes=scenes, force_fresh=force_fresh)
    if warning:
        graph["warning"] = warning
    return JSONResponse(graph)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


if FRONTEND_DIST.exists():
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets"
    )

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        candidate = (FRONTEND_DIST / full_path).resolve()
        if candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
