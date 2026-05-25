"""Pexels search + download."""
from __future__ import annotations
import hashlib
import requests
from pathlib import Path
from urllib.parse import urlencode
from app.config import settings

PEXELS_API = "https://api.pexels.com/videos/search"

def search(query: str, per_page: int = 8, orientation: str = "landscape") -> list[dict]:
    if not settings.PEXELS_API_KEY:
        return []
    headers = {"Authorization": settings.PEXELS_API_KEY, "User-Agent": "mpt-editor/0.1"}
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    url = f"{PEXELS_API}?{urlencode(params)}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        data = r.json()
    except Exception:
        return []
    out = []
    for v in data.get("videos", []) or []:
        # Prefer 1080p file
        files = v.get("video_files", []) or []
        best = None
        for f in files:
            if f.get("width") == 1920 and f.get("height") == 1080:
                best = f; break
        if not best:
            best = max(files, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0), default=None)
        if not best:
            continue
        out.append({
            "id": str(v["id"]),
            "url": best.get("link"),
            "duration": v.get("duration"),
            "preview_url": v.get("image"),
            "user": (v.get("user") or {}).get("name", ""),
            "query": query,
        })
    return out

def download(url: str, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, stream=True, timeout=30)
        if r.status_code != 200:
            return False
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(65536):
                if chunk:
                    f.write(chunk)
        return out_path.stat().st_size > 200_000
    except Exception:
        if out_path.exists():
            try: out_path.unlink()
            except: pass
        return False

def slug(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:14] + ".mp4"
