"""Re-render endpoint: reassemble MP4 from current project state."""
from __future__ import annotations
import asyncio
import math
import subprocess
import uuid
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.config import settings
from app.models.schema import RenderResponse
from app.storage import db
from app.services import render_service as rs
from app.services.events import events

router = APIRouter(prefix="/api/projects/{project_id}/render", tags=["render"])

CLIP_FULL = 5.0

async def _do_render(project_id: str, render_id: str) -> None:
    project = db.load(project_id)
    if not project:
        return
    try:
        await events.publish(project.id, {"type": "render_progress", "render_id": render_id, "progress": 5, "message": "trimming clips"})
        norm_root = settings.storage_path / "projects" / project_id / "normalized"
        trim_root = settings.storage_path / "projects" / project_id / "renders" / render_id / "trimmed"
        trim_root.mkdir(parents=True, exist_ok=True)
        concat_list: list[Path] = []
        for p in project.paragraphs:
            if not p.clips:
                continue
            target = p.audio_duration_sec
            # how many clips, and what's the last-clip duration?
            n = len(p.clips)
            full_durations = [min(c.duration_sec, CLIP_FULL) for c in p.clips[:-1]]
            last_dur = target - sum(full_durations)
            if last_dur < 0.5:
                # paragraph has too many clips for its audio; floor the last to 0.5s
                last_dur = 0.5
            for i, c in enumerate(p.clips):
                src = settings.storage_path / c.file_path
                if not src.exists(): continue
                planned = (last_dur if i == n - 1 else min(c.duration_sec, CLIP_FULL))
                actual = rs.probe_duration(src)
                if abs(actual - planned) < 0.05:
                    concat_list.append(src)
                else:
                    out = trim_root / f"p{p.id:02d}_{i:02d}.mp4"
                    await asyncio.to_thread(rs.trim_clip, src, out, planned)
                    concat_list.append(out)
        if not concat_list:
            raise RuntimeError("no clips to render")
        await events.publish(project.id, {"type": "render_progress", "render_id": render_id, "progress": 50, "message": "concatenating"})
        silent = settings.storage_path / "projects" / project_id / "renders" / render_id / "silent.mp4"
        silent.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(rs.concat_video, concat_list, silent)
        full_audio = settings.storage_path / (project.full_audio_path or "")
        if not full_audio.exists():
            raise RuntimeError("project audio missing")
        final = settings.storage_path / "projects" / project_id / "renders" / render_id / "final.mp4"
        await events.publish(project.id, {"type": "render_progress", "render_id": render_id, "progress": 80, "message": "muxing audio"})
        await asyncio.to_thread(rs.final_mux, silent, full_audio, final)
        project.final_video_path = str(final.relative_to(settings.storage_path))
        project.status = "rendered"
        db.save(project)
        await events.publish(project.id, {"type": "render_done", "render_id": render_id, "video_path": str(final.relative_to(settings.storage_path))})
    except Exception as e:
        await events.publish(project.id, {"type": "render_error", "render_id": render_id, "message": str(e)})

@router.post("", response_model=RenderResponse)
async def render(project_id: str, background: BackgroundTasks):
    project = db.load(project_id)
    if not project:
        raise HTTPException(404, "project not found")
    render_id = uuid.uuid4().hex[:12]
    background.add_task(_do_render, project_id, render_id)
    return RenderResponse(render_id=render_id, video_url=f"/api/files/projects/{project_id}/renders/{render_id}/final.mp4")
