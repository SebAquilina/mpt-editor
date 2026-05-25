"""YouTube discovery via yt-dlp + Gemini timestamp matching."""
from __future__ import annotations
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Optional
import yt_dlp
from google import genai
from google.genai import types
from app.config import settings

def search(query: str, n: int = 4) -> list[dict]:
    """Search YouTube via yt-dlp ytsearch (no API key)."""
    opts = {"quiet": True, "skip_download": True, "extract_flat": True, "noplaylist": True}
    out: list[dict] = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
            for e in info.get("entries", []) or []:
                if not e.get("id"):
                    continue
                out.append({
                    "id": e["id"],
                    "title": (e.get("title") or "")[:200],
                    "channel": e.get("channel") or e.get("uploader") or "",
                    "duration": e.get("duration"),
                    "url": f"https://www.youtube.com/watch?v={e['id']}",
                })
    except Exception:
        pass
    return out

def probe_duration(url: str) -> Optional[int]:
    opts = {"quiet": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return int(info["duration"])
    except Exception:
        return None

def find_segments(video_url: str, duration: int, paragraph_text: str, n: int = 4) -> list[dict]:
    """Ask Gemini to identify timestamp ranges in the video that match the paragraph."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = f"""Watching a YouTube tutorial.

CRITICAL: This video is EXACTLY {duration} SECONDS LONG. Any timestamp > {duration} is INVALID. Stay strictly within 0-{duration}.

We want short B-roll segments to illustrate this voice-over narration:
\"\"\"
{paragraph_text[:600]}
\"\"\"

Find up to {n} segments (each 4-7 seconds) where the VISUALS best match the narration. STRONG preference for:
- B-roll showing the action (close-ups of materials, tools, the process)
NOT: talking-head, intros/outros, watermarks, on-screen text-only frames, sponsorship segments.

Reply with COMPACT one-line JSON per segment, one per line, no markdown:
{{"start": <int 0-{duration}>, "end": <int 0-{duration}>, "visual": "<short desc>", "match": <0-1>, "talking_head": <true|false>}}

AT MOST {n} lines. If no good segments exist, output nothing.
"""
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[types.Content(parts=[
            types.Part(file_data=types.FileData(file_uri=video_url, mime_type="video/*")),
            types.Part(text=prompt),
        ])],
        config=types.GenerateContentConfig(
            temperature=0.3, max_output_tokens=2048,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    text = (resp.text or "").strip()
    segments: list[dict] = []
    for m in re.finditer(r"\{[^{}\n]*\}", text):
        try:
            d = json.loads(m.group(0))
            s, e = d.get("start"), d.get("end")
            if s is None or e is None:
                continue
            if not (0 <= s < e <= duration):
                continue
            if d.get("talking_head"):
                continue
            segments.append(d)
        except Exception:
            continue
    return segments

def _cookies_path() -> str | None:
    """Return path to YouTube cookies.txt if user has uploaded one. Lets yt-dlp pass the bot-check on cloud IPs."""
    from app.config import settings as _s
    p = _s.storage_path / "youtube_cookies.txt"
    return str(p) if p.exists() and p.stat().st_size > 100 else None

def download_segment(video_url: str, start: int, end: int, out_path: Path) -> bool:
    """Download a specific time range from a YouTube video. Falls back through three strategies."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base = [
        "yt-dlp", "-q",
        "--download-sections", f"*{start}-{end}",
        "--force-keyframes-at-cuts",
        # Required to solve YouTube's `n` challenge via deno (must be on PATH).
        "--remote-components", "ejs:github",
        "-f", "bestvideo[height<=1080][ext=mp4]/best[height<=1080][ext=mp4]/best",
        "--no-playlist",
        "-o", str(out_path),
    ]
    cookies = _cookies_path()
    strategies = []
    if cookies:
        # Strategy 1: with cookies (works around bot-check on cloud IPs)
        strategies.append(base + ["--cookies", cookies, video_url])
    # Strategy 2: alternative player clients (sometimes bypass anonymous-bot-check)
    strategies.append(base + ["--extractor-args", "youtube:player_client=mweb,android,tv", video_url])
    # Strategy 3: plain (works on residential IPs)
    strategies.append(base + [video_url])
    for cmd in strategies:
        try:
            subprocess.check_call(cmd, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            if out_path.exists() and out_path.stat().st_size > 50_000:
                return True
        except Exception:
            pass
        # Clean up partial file before next attempt
        if out_path.exists():
            try: out_path.unlink()
            except: pass
    return False

def score_candidates_by_title(candidates: list[dict], paragraph_text: str) -> list[dict]:
    """Lightweight title-keyword scoring used as a pre-filter."""
    tl = paragraph_text.lower()
    KEYWORDS = ['wax','wick','candle','fragrance','thermometer','melt','pour','soy','heat',
               'oil','wood','cotton','flame','beeswax','coconut','jar','dye','color','stir',
               'temperature','tutorial','how to','step','beginner']
    para_kws = {k for k in KEYWORDS if k in tl}
    scored = []
    for r in candidates:
        title_l = (r.get("title") or "").lower()
        score = sum(1 for k in para_kws if k in title_l)
        dur = r.get("duration") or 0
        dur_bonus = 1.0 if 60 < dur < 600 else 0.5 if 30 < dur < 1200 else 0.2
        r["_score"] = score + dur_bonus
        scored.append(r)
    return sorted(scored, key=lambda x: -x["_score"])
