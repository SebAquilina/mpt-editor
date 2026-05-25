"""Re-render endpoint: reassemble MP4 from current project state.

Resumable design: each trim is its own file on disk. If the background task
dies mid-render, the next invocation scans existing trims and skips them,
finishing only what's missing.
"""
from __future__ import annotations
import asyncio
import math
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.config import settings
from app.models.schema import RenderRecord, RenderResponse
from app.storage import db
from app.services import render_service as rs
from app.services.events import events

router = APIRouter(prefix="/api/projects/{project_id}/render", tags=["render"])

CLIP_FULL = 5.0
TRIM_BATCH = 25     # how many trims per yield-checkpoint, keeps event loop responsive
TRIM_CHECKPOINT_EVERY = 5   # how often to publish progress events

def _build_plan(project, trim_root: Path) -> tuple[list[Path], list[tuple[Path, Path, float]]]:
    """Return (final_concat_list, list_of_pending_trims).
    Already-trimmed clips that match planned duration on disk are reused as-is.
    """
    plan: list[Path] = []
    pending: list[tuple[Path, Path, float]] = []
    for para in project.paragraphs:
        if not para.clips:
            continue
        n = len(para.clips)
        target = para.audio_duration_sec
        full_durations = [min(c.duration_sec, CLIP_FULL) for c in para.clips[:-1]]
        last_dur = max(0.5, target - sum(full_durations))
        for i, c in enumerate(para.clips):
            src = settings.storage_path / c.file_path
            if not src.exists():
                continue
            planned = last_dur if i == n - 1 else min(c.duration_sec, CLIP_FULL)
            actual = rs.probe_duration(src)
            if abs(actual - planned) < 0.05:
                plan.append(src)
            else:
                out = trim_root / f"p{para.id:02d}_{i:02d}.mp4"
                if out.exists() and out.stat().st_size > 1000 and abs(rs.probe_duration(out) - planned) < 0.05:
                    # already trimmed in a previous (interrupted) render
                    plan.append(out)
                else:
                    pending.append((src, out, planned))
                    plan.append(out)
    return plan, pending

def _record(project, render_id: str) -> RenderRecord:
    for r in project.renders:
        if r.id == render_id:
            return r
    r = RenderRecord(id=render_id, status="pending")
    project.renders.append(r)
    return r

async def _do_render(project_id: str, render_id: str) -> None:
    project = db.load(project_id)
    if not project:
        return
    rec = _record(project, render_id)
    try:
        rec.status = "rendering"
        db.save(project)

        trim_root = settings.storage_path / "projects" / project_id / "renders" / render_id / "trimmed"
        trim_root.mkdir(parents=True, exist_ok=True)

        await events.publish(project.id, {"type": "render_progress", "render_id": render_id, "progress": 3, "message": "planning"})
        concat_list, pending_trims = _build_plan(project, trim_root)
        if not concat_list:
            raise RuntimeError("no clips to render")

        # Trim in batches with yield points so progress events are flushed and
        # we can survive long sessions without blocking the loop.
        total_pending = len(pending_trims)
        done_trims = 0
        for idx, (src, dst, dur) in enumerate(pending_trims):
            await asyncio.to_thread(rs.trim_clip, src, dst, dur)
            done_trims += 1
            if done_trims % TRIM_CHECKPOINT_EVERY == 0 or done_trims == total_pending:
                pct = 10 + 60 * (done_trims / max(1, total_pending))
                await events.publish(project.id, {
                    "type": "render_progress", "render_id": render_id,
                    "progress": round(pct, 1),
                    "message": f"trimmed {done_trims}/{total_pending}",
                })
            if done_trims % TRIM_BATCH == 0:
                await asyncio.sleep(0)  # yield to other tasks

        await events.publish(project.id, {"type": "render_progress", "render_id": render_id, "progress": 78, "message": "concatenating"})
        silent = settings.storage_path / "projects" / project_id / "renders" / render_id / "silent.mp4"
        await asyncio.to_thread(rs.concat_video, concat_list, silent)

        full_audio = settings.storage_path / (project.full_audio_path or "")
        if not full_audio.exists():
            raise RuntimeError("project audio missing")

        final = settings.storage_path / "projects" / project_id / "renders" / render_id / "final.mp4"
        await events.publish(project.id, {"type": "render_progress", "render_id": render_id, "progress": 90, "message": "muxing audio"})
        await asyncio.to_thread(rs.final_mux, silent, full_audio, final)

        if not final.exists():
            raise RuntimeError("final mux failed")

        # Record success
        rec.status = "complete"
        rec.video_path = str(final.relative_to(settings.storage_path))
        rec.duration_sec = rs.probe_duration(final)
        rec.completed_at = datetime.utcnow()
        # Keep final_video_path as the latest render (back-compat with editor preview)
        project.final_video_path = rec.video_path
        project.status = "rendered"
        db.save(project)

        await events.publish(project.id, {
            "type": "render_done", "render_id": render_id,
            "video_path": rec.video_path,
        })

    except Exception as e:
        rec.status = "failed"
        rec.error_message = str(e)
        rec.completed_at = datetime.utcnow()
        db.save(project)
        await events.publish(project.id, {"type": "render_error", "render_id": render_id, "message": str(e)})

@router.post("", response_model=RenderResponse)
async def render(project_id: str, background: BackgroundTasks):
    project = db.load(project_id)
    if not project:
        raise HTTPException(404, "project not found")
    render_id = uuid.uuid4().hex[:12]
    background.add_task(_do_render, project_id, render_id)
    return RenderResponse(render_id=render_id, video_url=f"/api/files/projects/{project_id}/renders/{render_id}/final.mp4")

@router.get("s")
async def list_renders(project_id: str):
    """GET /api/projects/{id}/renders — full render history (newest last)."""
    project = db.load(project_id)
    if not project:
        raise HTTPException(404, "project not found")
    return {"renders": [r.model_dump() for r in project.renders]}

@router.post("/{render_id}/resume", response_model=RenderResponse)
async def resume_render(project_id: str, render_id: str, background: BackgroundTasks):
    """Resume a render that was interrupted. Re-runs _do_render which scans existing trims."""
    project = db.load(project_id)
    if not project:
        raise HTTPException(404, "project not found")
    rec = next((r for r in project.renders if r.id == render_id), None)
    if not rec:
        raise HTTPException(404, "render not found")
    if rec.status == "complete":
        raise HTTPException(409, "render already complete")
    background.add_task(_do_render, project_id, render_id)
    return RenderResponse(render_id=render_id, video_url=f"/api/files/projects/{project_id}/renders/{render_id}/final.mp4")
