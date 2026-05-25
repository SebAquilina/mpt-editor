"""Pipeline orchestrator: prompt -> script -> TTS -> search -> match -> download -> ready.

Resumable: each phase checks current project status and skips itself if past that phase.
Clip state is persisted incrementally so partial work survives process death.
"""
from __future__ import annotations
import asyncio
import math
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

PHASE_ORDER = [
    "queued", "generating_script", "generating_tts", "searching",
    "matching", "downloading", "normalizing", "ready",
]

def _phase_at_or_past(current: str, target: str) -> bool:
    try:
        return PHASE_ORDER.index(current) >= PHASE_ORDER.index(target)
    except ValueError:
        return False

async def emit(project: Project, status: str, progress: float, msg: str = "") -> None:
    project.status = status
    project.progress = progress
    project.progress_message = msg
    db.save(project)
    await events.publish(project.id, {"type": "progress", "status": status, "progress": progress, "message": msg})

async def run_pipeline(project_id: str, target_paragraphs: int = 18) -> None:
    project = db.load(project_id)
    if not project:
        return
    try:
        # ── 1. Script ──────────────────────────────────────────────────────────
        paragraphs_text: list[str]
        if not project.paragraphs:
            await emit(project, "generating_script", 5, "Writing script via Gemini…")
            script_text = await asyncio.to_thread(script_svc.generate_script, project.prompt, "en-US", target_paragraphs)
            paragraphs_text = [p.strip() for p in script_text.split("\n\n") if p.strip()]
            if not paragraphs_text:
                raise RuntimeError("Gemini returned an empty script")
            project.title = (await asyncio.to_thread(script_svc.generate_title, project.prompt)) or project.prompt[:60]
            # Persist text-only paragraphs so we can resume
            project.paragraphs = [
                Paragraph(id=i, text=p, audio_path="", audio_duration_sec=0, timeline_start_sec=0)
                for i, p in enumerate(paragraphs_text)
            ]
            await emit(project, "generating_script", 12, f"{sum(len(p.split()) for p in paragraphs_text)} words / {len(paragraphs_text)} paragraphs")
        else:
            paragraphs_text = [p.text for p in project.paragraphs]
            await emit(project, project.status, project.progress, "Resuming…")

        # ── 2. TTS ─────────────────────────────────────────────────────────────
        if not _phase_at_or_past(project.status, "searching"):
            await emit(project, "generating_tts", 18, "Synthesizing narration…")
            tts_dir = settings.storage_path / "projects" / project_id / "audio"
            audio_paths = await tts_svc.synthesize_all(paragraphs_text, settings.DEFAULT_VOICE, tts_dir)
            cumulative = 0.0
            for i, (ptext, apath) in enumerate(zip(paragraphs_text, audio_paths)):
                dur = rs.probe_duration(apath)
                stext_list = tts_svc.split_into_sentences(ptext)
                total_words = sum(len(s.split()) for s in stext_list) or 1
                s_start = cumulative
                sents = []
                for s in stext_list:
                    wc = len(s.split())
                    s_dur = dur * (wc / total_words)
                    sents.append(Sentence(text=s, start_sec=s_start, end_sec=s_start + s_dur, paragraph_id=i))
                    s_start += s_dur
                p = project.paragraphs[i]
                p.audio_path = str(apath.relative_to(settings.storage_path))
                p.audio_duration_sec = dur
                p.timeline_start_sec = cumulative
                p.sentences = sents
                cumulative += dur
            full_audio = settings.storage_path / "projects" / project_id / "audio_full.mp3"
            rs.concat_audio(audio_paths, full_audio)
            project.full_audio_path = str(full_audio.relative_to(settings.storage_path))
            db.save(project)

        # ── 3. Queries ─────────────────────────────────────────────────────────
        if not _phase_at_or_past(project.status, "matching") or not project.paragraphs[0].search_queries:
            await emit(project, "searching", 28, "Generating per-paragraph queries…")
            qmap = await asyncio.to_thread(script_svc.generate_paragraph_queries, paragraphs_text)
            for p in project.paragraphs:
                p.search_queries = qmap.get(p.id, [p.text[:40]])
            db.save(project)

        # ── 4. YouTube discovery + matching per paragraph ──────────────────────
        clip_dir = settings.storage_path / "projects" / project_id / "clips"
        norm_dir = settings.storage_path / "projects" / project_id / "normalized"
        thumb_dir = settings.storage_path / "projects" / project_id / "thumbnails"

        if not _phase_at_or_past(project.status, "ready"):
            for pi, p in enumerate(project.paragraphs):
                yt_done_this_paragraph = any(c.source == "youtube" for c in p.clips)
                if not yt_done_this_paragraph:
                    await emit(project, "matching", 32 + 40 * pi / max(1, len(project.paragraphs)),
                               f"Matching paragraph {pi+1}/{len(project.paragraphs)}…")
                    # Search
                    seen = set(); cands = []
                    for q in p.search_queries[:2]:
                        for r in await asyncio.to_thread(yt.search, q, 4):
                            if r["id"] in seen: continue
                            seen.add(r["id"]); cands.append(r)
                    cands = yt.score_candidates_by_title(cands, p.text)
                    chosen_segs = []
                    for c in cands[:2]:
                        d = c.get("duration") or 0
                        if d <= 30 or d > 1800: continue
                        try:
                            segs = await asyncio.to_thread(yt.find_segments, c["url"], int(d), p.text, 4)
                        except Exception:
                            segs = []
                        if segs:
                            chosen_segs = [{**s, "video": c} for s in segs]
                            break
                    # Download + normalize each segment, save state per-clip
                    for idx, s in enumerate(chosen_segs):
                        v = s["video"]
                        st, en = max(0, int(s["start"]) - 1), int(s["end"]) + 1
                        raw = clip_dir / f"P{p.id}_{idx:02d}_{v['id']}_{st}-{en}.mp4"
                        norm = norm_dir / raw.name
                        thumb = thumb_dir / (raw.stem + ".jpg")
                        if not raw.exists():
                            if not await asyncio.to_thread(yt.download_segment, v["url"], st, en, raw):
                                continue
                        if not norm.exists():
                            if not await asyncio.to_thread(rs.normalize_clip, raw, norm, f"via {v.get('channel','')[:30]} on YouTube"):
                                continue
                        if not thumb.exists():
                            await asyncio.to_thread(rs.thumbnail, norm, thumb)
                        actual = rs.probe_duration(norm)
                        p.clips.append(Clip(
                            source="youtube",
                            file_path=str(norm.relative_to(settings.storage_path)),
                            thumbnail_path=str(thumb.relative_to(settings.storage_path)) if thumb.exists() else None,
                            duration_sec=min(actual, CLIP_DURATION),
                            paragraph_id=p.id, order_in_paragraph=len(p.clips),
                            visual_description=s.get("visual"), match_quality=s.get("match"),
                            yt_video_id=v["id"], yt_channel=v.get("channel"),
                            yt_video_title=v.get("title"), yt_video_url=v["url"],
                            yt_start_sec=float(st), yt_end_sec=float(en),
                        ))
                        db.save(project)  # persist after every clip

                # Fill remainder with Pexels
                elapsed = sum(c.duration_sec for c in p.clips)
                remaining = p.audio_duration_sec - elapsed
                needed = max(0, math.ceil(remaining / CLIP_DURATION))
                if needed > 0 and not any(c.source == "pexels" for c in p.clips):
                    pex_results: list[dict] = []
                    seen_pex = set()
                    for q in p.search_queries[:2]:
                        for r in await asyncio.to_thread(pexels.search, q, 4):
                            if r["id"] in seen_pex: continue
                            seen_pex.add(r["id"]); pex_results.append(r)
                    for idx, pr in enumerate(pex_results[:needed]):
                        raw = clip_dir / f"P{p.id}_pex_{idx:02d}_{pexels.slug(pr['url'])}"
                        norm = norm_dir / raw.name
                        thumb = thumb_dir / (raw.stem + ".jpg")
                        if not raw.exists():
                            if not await asyncio.to_thread(pexels.download, pr["url"], raw): continue
                        if not norm.exists():
                            if not await asyncio.to_thread(rs.normalize_clip, raw, norm, None): continue
                        if not thumb.exists():
                            await asyncio.to_thread(rs.thumbnail, norm, thumb)
                        actual = rs.probe_duration(norm)
                        p.clips.append(Clip(
                            source="pexels",
                            file_path=str(norm.relative_to(settings.storage_path)),
                            thumbnail_path=str(thumb.relative_to(settings.storage_path)) if thumb.exists() else None,
                            duration_sec=min(actual, CLIP_DURATION),
                            paragraph_id=p.id, order_in_paragraph=len(p.clips),
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
