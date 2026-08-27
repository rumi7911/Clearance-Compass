"""FastAPI app: one endpoint that runs the pipeline, plus the built frontend."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .data.parse_script import ScriptValidationError, format_scenes_as_script, parse_and_validate
from .data.scenes import SCENES
from .pipeline import run_pipeline

app = FastAPI(title="Clearance Compass")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# The pipeline is a single sequential run against a shared Gemini quota
# (see pipeline.py's _GEMINI_CONCURRENCY). A second concurrent run doesn't
# fail cleanly -- it doubles quota contention and both requests eventually
# time out. Reject a second call outright instead of racing them.
_analysis_lock = asyncio.Lock()


class AnalyzeRequest(BaseModel):
    script: str | None = None
    force_fresh: bool = False


@app.get("/api/demo-script")
async def demo_script() -> dict:
    return {"script": format_scenes_as_script(SCENES)}


@app.post("/api/analyze")
async def analyze(body: AnalyzeRequest | None = Body(default=None)) -> JSONResponse:
    if _analysis_lock.locked():
        raise HTTPException(
            status_code=409,
            detail="An analysis is already running. Wait for it to finish before starting another.",
        )

    scenes = None
    warning = None
    if body is not None and body.script is not None:
        try:
            scenes, warning = parse_and_validate(body.script)
        except ScriptValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    force_fresh = body.force_fresh if body is not None else False
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
