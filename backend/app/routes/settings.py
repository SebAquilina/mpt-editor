"""Runtime API key management.

Keys are entered through the UI, persisted to the gitignored .env file, and
hot-loaded into settings without restarting the server. The .env file is read
on next process startup so values survive restarts.
"""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_PATH = Path(__file__).resolve().parents[3] / "backend" / ".env"
# Fallback to a backend-relative path if the resolution above mis-fires
if not ENV_PATH.parent.exists():
    ENV_PATH = Path("backend/.env").resolve()

class KeysResponse(BaseModel):
    gemini_configured: bool
    pexels_configured: bool
    gemini_masked: str | None = None
    pexels_masked: str | None = None

class KeysUpdate(BaseModel):
    gemini_api_key: str | None = None
    pexels_api_key: str | None = None

def _mask(key: str) -> str | None:
    if not key: return None
    return key[:6] + "…" + key[-4:] if len(key) > 12 else "***"

def _write_env(updates: dict[str, str]) -> None:
    """Update the .env file in-place, preserving other keys."""
    existing: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v
    existing.update(updates)
    tmp = ENV_PATH.with_suffix(".env.tmp")
    tmp.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")
    tmp.replace(ENV_PATH)

@router.get("/keys", response_model=KeysResponse)
async def get_keys():
    return KeysResponse(
        gemini_configured=bool(settings.GEMINI_API_KEY),
        pexels_configured=bool(settings.PEXELS_API_KEY),
        gemini_masked=_mask(settings.GEMINI_API_KEY),
        pexels_masked=_mask(settings.PEXELS_API_KEY),
    )

@router.put("/keys", response_model=KeysResponse)
async def update_keys(body: KeysUpdate):
    """Update API keys. Writes them to .env (gitignored) AND updates the live settings object."""
    updates: dict[str, str] = {}
    if body.gemini_api_key is not None:
        settings.GEMINI_API_KEY = body.gemini_api_key.strip()
        updates["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
    if body.pexels_api_key is not None:
        settings.PEXELS_API_KEY = body.pexels_api_key.strip()
        updates["PEXELS_API_KEY"] = settings.PEXELS_API_KEY
    if not updates:
        raise HTTPException(400, "no keys provided")
    try:
        _write_env(updates)
    except Exception as e:
        # Live update still works even if .env write fails
        raise HTTPException(500, f"updated in-memory but failed to persist to .env: {e}")
    return await get_keys()


# ─── YouTube cookies (upload once, gets used by yt-dlp for downloads) ─────────
from fastapi import UploadFile, File
from pathlib import Path as _P

def _yt_cookies_path() -> _P:
    return settings.storage_path / "youtube_cookies.txt"

class CookiesStatus(BaseModel):
    uploaded: bool
    size_bytes: int = 0

@router.get("/youtube-cookies", response_model=CookiesStatus)
async def get_cookies_status():
    p = _yt_cookies_path()
    if p.exists() and p.stat().st_size > 100:
        return CookiesStatus(uploaded=True, size_bytes=p.stat().st_size)
    return CookiesStatus(uploaded=False)

@router.post("/youtube-cookies", response_model=CookiesStatus)
async def upload_cookies(file: UploadFile = File(...)):
    p = _yt_cookies_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    # Basic sanity check: must look like a Netscape cookies.txt
    if len(content) < 100:
        raise HTTPException(400, "cookies file too small — must be a valid Netscape cookies.txt with at least YouTube SID/SAPISID rows")
    if b".youtube.com" not in content:
        raise HTTPException(400, "cookies file doesn't contain any .youtube.com cookies — wrong file?")
    p.write_bytes(content)
    return CookiesStatus(uploaded=True, size_bytes=len(content))

@router.delete("/youtube-cookies")
async def delete_cookies():
    p = _yt_cookies_path()
    if p.exists(): p.unlink()
    return {"ok": True}
