"""Clip edit endpoints: delete-with-alternates, replace, reorder, upload, search."""
from __future__ import annotations
import asyncio
from pathlib import Path
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.config import settings
from app.models.schema import (
    Clip, ReorderRequest, AlternatesResponse, SearchClipRequest, SearchClipResponse, ReplaceClipRequest
)
from app.storage import db
from app.services import youtube as yt
from app.services import pexels
from app.services import render_service as rs

router = APIRouter(prefix="/api/projects/{project_id}/clips", tags=["clips"])

def _find_clip(project, clip_id: str) -> tuple[int, int] | None:
    for pi, p in enumerate(project.paragraphs):
        for ci, c in enumerate(p.clips):
            if c.id == clip_id: return (pi, ci)
    return None

@router.post("/reorder")
async def reorder(project_id: str, body: ReorderRequest):
    project = db.load(project_id)
    if not project: raise HTTPException(404, "project not found")
    p = next((x for x in project.paragraphs if x.id == body.paragraph_id), None)
    if not p: raise HTTPException(404, "paragraph not found")
    by_id = {c.id: c for c in p.clips}
    new_order = [by_id[cid] for cid in body.ordered_clip_ids if cid in by_id]
    if len(new_order) != len(p.clips):
        raise HTTPException(400, "reorder list must contain every clip exactly once")
    for i, c in enumerate(new_order):
        c.order_in_paragraph = i
    p.clips = new_order
    db.save(project)
    return {"ok": True}

@router.post("/{clip_id}/alternates", response_model=AlternatesResponse)
async def get_alternates(project_id: str, clip_id: str):
    """Find 3 alternate clips for the same paragraph using a fresh search."""
    project = db.load(project_id)
    if not project: raise HTTPException(404, "project not found")
    pos = _find_clip(project, clip_id)
    if not pos: raise HTTPException(404, "clip not found")
    pi, ci = pos
    paragraph = project.paragraphs[pi]
    clip = paragraph.clips[ci]
    existing_video_ids = {c.yt_video_id for c in paragraph.clips if c.yt_video_id}

    # 1) Search YouTube with paragraph's queries
    candidates: list[dict] = []
    for q in paragraph.search_queries[:2]:
        for r in await asyncio.to_thread(yt.search, q, 4):
            if r["id"] in existing_video_ids: continue
            candidates.append(r)
    candidates = yt.score_candidates_by_title(candidates, paragraph.text)[:3]

    # 2) Ask Gemini for 1 segment from each + download + normalize
    alternates: list[Clip] = []
    clip_dir = settings.storage_path / "projects" / project_id / "clips"
    norm_dir = settings.storage_path / "projects" / project_id / "normalized"
    thumb_dir = settings.storage_path / "projects" / project_id / "thumbnails"
    for c in candidates:
        d = c.get("duration") or 0
        if d <= 30 or d > 1800: continue
        try:
            segs = await asyncio.to_thread(yt.find_segments, c["url"], int(d), paragraph.text, 1)
        except Exception:
            segs = []
        if not segs: continue
        s = segs[0]
        st, en = max(0, int(s["start"]) - 1), int(s["end"]) + 1
        raw = clip_dir / f"alt_{c['id']}_{st}-{en}.mp4"
        norm = norm_dir / raw.name
        thumb = thumb_dir / (raw.stem + ".jpg")
        if not raw.exists():
            if not await asyncio.to_thread(yt.download_segment, c["url"], st, en, raw): continue
        if not norm.exists():
            await asyncio.to_thread(rs.normalize_clip, raw, norm, f"via {c.get('channel','')[:30]} on YouTube")
        if not thumb.exists():
            await asyncio.to_thread(rs.thumbnail, norm, thumb)
        actual = rs.probe_duration(norm)
        alt = Clip(
            source="youtube",
            file_path=str(norm.relative_to(settings.storage_path)),
            thumbnail_path=str(thumb.relative_to(settings.storage_path)) if thumb.exists() else None,
            duration_sec=min(actual, 5.0),
            paragraph_id=paragraph.id, order_in_paragraph=clip.order_in_paragraph,
            visual_description=s.get("visual"), match_quality=s.get("match"),
            yt_video_id=c["id"], yt_channel=c.get("channel"),
            yt_video_title=c.get("title"), yt_video_url=c["url"],
            yt_start_sec=float(st), yt_end_sec=float(en),
        )
        alternates.append(alt)
        if len(alternates) >= 3: break
    return AlternatesResponse(alternates=alternates)

@router.post("/{clip_id}/search", response_model=SearchClipResponse)
async def search_replace(project_id: str, clip_id: str, body: SearchClipRequest):
    """Live search for replacement clips."""
    project = db.load(project_id)
    if not project: raise HTTPException(404, "project not found")
    pos = _find_clip(project, clip_id)
    if not pos: raise HTTPException(404, "clip not found")
    pi, ci = pos
    paragraph = project.paragraphs[pi]

    results: list[Clip] = []
    if body.source in ("youtube", "both"):
        yt_results = await asyncio.to_thread(yt.search, body.query, 6)
        # Return as stub clips — full materialization happens on replace
        for r in yt_results[:6]:
            results.append(Clip(
                source="youtube", file_path="",  # not materialized yet
                thumbnail_path=f"https://i.ytimg.com/vi/{r['id']}/mqdefault.jpg",
                duration_sec=min(r.get("duration") or 0, 5.0),
                paragraph_id=paragraph.id, order_in_paragraph=0,
                yt_video_id=r["id"], yt_channel=r.get("channel"),
                yt_video_title=r.get("title"), yt_video_url=r["url"],
            ))
    if body.source in ("pexels", "both"):
        pex = await asyncio.to_thread(pexels.search, body.query, 6)
        for r in pex[:6]:
            results.append(Clip(
                source="pexels", file_path="",
                thumbnail_path=r.get("preview_url"),
                duration_sec=min(r.get("duration") or 0, 5.0),
                paragraph_id=paragraph.id, order_in_paragraph=0,
                pexels_id=r["id"], pexels_url=r.get("url"), pexels_query=body.query,
            ))
    return SearchClipResponse(results=results)

@router.put("/{clip_id}")
async def replace_clip(project_id: str, clip_id: str, body: ReplaceClipRequest):
    """Replace a clip with an alternate/search-result/upload Clip object (by id)."""
    project = db.load(project_id)
    if not project: raise HTTPException(404, "project not found")
    pos = _find_clip(project, clip_id)
    if not pos: raise HTTPException(404, "clip not found")
    pi, ci = pos
    paragraph = project.paragraphs[pi]
    # In a polished system we'd look up the clip from a session cache; for now,
    # accept the full Clip dict in body.new_clip_id (frontend posts it as the id of a Clip we already
    # returned to it from alternates/search/upload).
    # Here we assume new_clip_id is actually the file_path of a normalized clip.
    new_path = settings.storage_path / body.new_clip_id
    if not new_path.exists():
        raise HTTPException(400, f"new clip file not found: {body.new_clip_id}")
    old = paragraph.clips[ci]
    new_clip = Clip(
        source="upload",
        file_path=body.new_clip_id,
        thumbnail_path=None,
        duration_sec=rs.probe_duration(new_path),
        paragraph_id=paragraph.id,
        order_in_paragraph=old.order_in_paragraph,
    )
    paragraph.clips[ci] = new_clip
    db.save(project)
    return {"ok": True, "clip_id": new_clip.id}

@router.post("/{clip_id}/upload")
async def upload_replacement(project_id: str, clip_id: str, file: UploadFile = File(...)):
    """Upload an MP4 to replace a clip. Normalizes it and slots it in."""
    project = db.load(project_id)
    if not project: raise HTTPException(404, "project not found")
    pos = _find_clip(project, clip_id)
    if not pos: raise HTTPException(404, "clip not found")
    pi, ci = pos
    paragraph = project.paragraphs[pi]
    old = paragraph.clips[ci]

    uploads_dir = settings.storage_path / "uploads" / project_id
    uploads_dir.mkdir(parents=True, exist_ok=True)
    raw = uploads_dir / f"{uuid.uuid4().hex[:12]}.mp4"
    raw.write_bytes(await file.read())

    norm_dir = settings.storage_path / "projects" / project_id / "normalized"
    thumb_dir = settings.storage_path / "projects" / project_id / "thumbnails"
    norm = norm_dir / f"upload_{raw.stem}.mp4"
    thumb = thumb_dir / f"upload_{raw.stem}.jpg"
    await asyncio.to_thread(rs.normalize_clip, raw, norm, None)
    await asyncio.to_thread(rs.thumbnail, norm, thumb)

    new_clip = Clip(
        source="upload",
        file_path=str(norm.relative_to(settings.storage_path)),
        thumbnail_path=str(thumb.relative_to(settings.storage_path)) if thumb.exists() else None,
        duration_sec=min(rs.probe_duration(norm), 5.0),
        paragraph_id=paragraph.id, order_in_paragraph=old.order_in_paragraph,
        upload_filename=file.filename,
    )
    paragraph.clips[ci] = new_clip
    db.save(project)
    return {"ok": True, "clip_id": new_clip.id, "thumbnail_path": new_clip.thumbnail_path}

@router.delete("/{clip_id}")
async def delete_clip(project_id: str, clip_id: str):
    """Hard-delete a clip. Frontend should normally trigger the alternates flow first."""
    project = db.load(project_id)
    if not project: raise HTTPException(404, "project not found")
    pos = _find_clip(project, clip_id)
    if not pos: raise HTTPException(404, "clip not found")
    pi, ci = pos
    paragraph = project.paragraphs[pi]
    paragraph.clips.pop(ci)
    for i, c in enumerate(paragraph.clips):
        c.order_in_paragraph = i
    db.save(project)
    return {"ok": True}
