"""Pipeline orchestrator: prompt -> script -> TTS -> search -> match -> download -> normalize -> ready."""
from __future__ import annotations
import asyncio
import json
import math
import uuid
from pathlib import Path
from app.config import settings
from app.models.schema import Project, Paragraph, Sentence, Clip
from app.services import script as script_svc
from app.services import tts as tts_svc
from app.services import youtube as yt
from app.services import pexels
from app.services import render_service as rs
from app.services.events import events
from app.storage import db

CLIP_DURATION = 5.0

async def emit(project: Project, status: str, progress: float, msg: str = "") -> None:
    project.status = status
    project.progress = progress
    project.progress_message = msg
    db.save(project)
    await events.publish(project.id, {"type": "progress", "status": status, "progress": progress, "message": msg})

async def run_pipeline(project_id: str) -> None:
    """Run the full pipeline. Saves state at every checkpoint so it's restartable in principle."""
    project = db.load(project_id)
    if not project:
        return
    try:
        # 1. Script
        await emit(project, "generating_script", 5, "Asking Gemini to write the script…")
        script_text = await asyncio.to_thread(script_svc.generate_script, project.prompt)
        paragraphs_text = [p.strip() for p in script_text.split("\n\n") if p.strip()]
        if not paragraphs_text:
            raise RuntimeError("Gemini returned an empty script")
        await emit(project, "generating_script", 12, f"Script: {sum(len(p.split()) for p in paragraphs_text)} words / {len(paragraphs_text)} paragraphs")

        title = await asyncio.to_thread(script_svc.generate_title, project.prompt, script_text)
        project.title = title or project.prompt[:60]

        # 2. TTS
        await emit(project, "generating_tts", 18, "Synthesizing narration…")
        tts_dir = settings.storage_path / "projects" / project_id / "audio"
        audio_paths = await tts_svc.synthesize_all(paragraphs_text, settings.DEFAULT_VOICE, tts_dir)

        # Build Paragraph + Sentence objects with absolute timeline positions
        cumulative = 0.0
        paragraphs: list[Paragraph] = []
        for i, (ptext, apath) in enumerate(zip(paragraphs_text, audio_paths)):
            dur = rs.probe_duration(apath)
            sentences = []
            stext_list = tts_svc.split_into_sentences(ptext)
            # Rough timing: split paragraph duration proportionally by word count
            total_words = sum(len(s.split()) for s in stext_list) or 1
            s_start = cumulative
            for s in stext_list:
                wc = len(s.split())
                s_dur = dur * (wc / total_words)
                sentences.append(Sentence(text=s, start_sec=s_start, end_sec=s_start + s_dur, paragraph_id=i))
                s_start += s_dur
            paragraphs.append(Paragraph(
                id=i, text=ptext,
                audio_path=str(apath.relative_to(settings.storage_path)),
                audio_duration_sec=dur,
                timeline_start_sec=cumulative,
                sentences=sentences,
            ))
            cumulative += dur
        project.paragraphs = paragraphs

        # Build concat audio (project-level)
        full_audio = settings.storage_path / "projects" / project_id / "audio_full.mp3"
        rs.concat_audio(audio_paths, full_audio)
        project.full_audio_path = str(full_audio.relative_to(settings.storage_path))
        db.save(project)

        # 3. Search queries
        await emit(project, "searching", 25, "Generating per-paragraph search queries…")
        query_map = await asyncio.to_thread(script_svc.generate_paragraph_queries, paragraphs_text)
        for p in project.paragraphs:
            p.search_queries = query_map.get(p.id, [])
        db.save(project)

        # 4. YouTube search across all paragraphs
        await emit(project, "searching", 32, "Searching YouTube for candidate clips…")
        yt_per_para: dict[int, list[dict]] = {}
        for p in project.paragraphs:
            seen = set(); cands = []
            for q in p.search_queries[:2]:
                for r in await asyncio.to_thread(yt.search, q, 4):
                    if r["id"] in seen: continue
                    seen.add(r["id"]); r["source_query"] = q
                    cands.append(r)
            yt_per_para[p.id] = yt.score_candidates_by_title(cands, p.text)

        # 5. Gemini matching for top candidate per paragraph
        await emit(project, "matching", 45, "Asking Gemini which moments match…")
        chosen_segs: dict[int, list[dict]] = {}
        for p in project.paragraphs:
            cands = yt_per_para.get(p.id, [])
            for c in cands[:2]:
                d = c.get("duration") or 0
                if d <= 30 or d > 1800: continue
                try:
                    segs = await asyncio.to_thread(yt.find_segments, c["url"], int(d), p.text, 4)
                    if segs:
                        chosen_segs[p.id] = [{**s, "video": c} for s in segs]
                        break
                except Exception:
                    continue

        # 6. Download segments
        await emit(project, "downloading", 60, "Downloading clips from YouTube…")
        clip_dir = settings.storage_path / "projects" / project_id / "clips"
        norm_dir = settings.storage_path / "projects" / project_id / "normalized"
        thumb_dir = settings.storage_path / "projects" / project_id / "thumbnails"
        for p in project.paragraphs:
            segs = chosen_segs.get(p.id, [])
            # YouTube clips first
            for idx, s in enumerate(segs):
                v = s["video"]
                st, en = max(0, int(s["start"]) - 1), int(s["end"]) + 1
                raw = clip_dir / f"P{p.id}_{idx:02d}_{v['id']}_{st}-{en}.mp4"
                norm = norm_dir / raw.name
                thumb = thumb_dir / (raw.stem + ".jpg")
                if not raw.exists():
                    ok = await asyncio.to_thread(yt.download_segment, v["url"], st, en, raw)
                    if not ok: continue
                if not norm.exists():
                    await asyncio.to_thread(rs.normalize_clip, raw, norm, f"via {v.get('channel','')[:30]} on YouTube")
                if not thumb.exists():
                    await asyncio.to_thread(rs.thumbnail, norm, thumb)
                actual = rs.probe_duration(norm)
                p.clips.append(Clip(
                    source="youtube",
                    file_path=str(norm.relative_to(settings.storage_path)),
                    thumbnail_path=str(thumb.relative_to(settings.storage_path)) if thumb.exists() else None,
                    duration_sec=min(actual, CLIP_DURATION),
                    paragraph_id=p.id,
                    order_in_paragraph=len(p.clips),
                    visual_description=s.get("visual"),
                    match_quality=s.get("match"),
                    yt_video_id=v["id"], yt_channel=v.get("channel"),
                    yt_video_title=v.get("title"), yt_video_url=v["url"],
                    yt_start_sec=float(st), yt_end_sec=float(en),
                ))

        # 7. Fill remainder with Pexels
        await emit(project, "downloading", 78, "Filling remainder with Pexels…")
        for p in project.paragraphs:
            elapsed = sum(c.duration_sec for c in p.clips)
            remaining = p.audio_duration_sec - elapsed
            needed = max(0, math.ceil(remaining / CLIP_DURATION))
            if needed == 0: continue
            results: list[dict] = []
            for q in p.search_queries[:2]:
                results.extend(await asyncio.to_thread(pexels.search, q, 4))
            # Dedupe
            seen = set(); deduped = []
            for r in results:
                if r["id"] in seen: continue
                seen.add(r["id"]); deduped.append(r)
            for idx, pr in enumerate(deduped[:needed]):
                fname = pexels.slug(pr["url"])
                raw = clip_dir / f"P{p.id}_pex_{idx:02d}_{fname}"
                norm = norm_dir / raw.name
                thumb = thumb_dir / (raw.stem + ".jpg")
                if not raw.exists():
                    if not await asyncio.to_thread(pexels.download, pr["url"], raw): continue
                if not norm.exists():
                    await asyncio.to_thread(rs.normalize_clip, raw, norm, None)
                if not thumb.exists():
                    await asyncio.to_thread(rs.thumbnail, norm, thumb)
                actual = rs.probe_duration(norm)
                p.clips.append(Clip(
                    source="pexels",
                    file_path=str(norm.relative_to(settings.storage_path)),
                    thumbnail_path=str(thumb.relative_to(settings.storage_path)) if thumb.exists() else None,
                    duration_sec=min(actual, CLIP_DURATION),
                    paragraph_id=p.id,
                    order_in_paragraph=len(p.clips),
                    pexels_id=pr["id"], pexels_url=pr.get("preview_url"),
                    pexels_query=pr.get("query"),
                ))

        db.save(project)
        await emit(project, "ready", 100, "Ready to edit")
        await events.publish(project.id, {"type": "done"})

    except Exception as e:
        project.error_message = str(e)
        await emit(project, "error", project.progress, f"Pipeline failed: {e}")
        await events.publish(project.id, {"type": "error", "message": str(e)})
