"""Serve clip/audio/video files from STORAGE_DIR."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.config import settings

router = APIRouter(prefix="/api/files", tags=["files"])

@router.get("/{path:path}")
async def serve_file(path: str):
    fp = (settings.storage_path / path).resolve()
    if settings.storage_path.resolve() not in fp.parents and fp != settings.storage_path:
        raise HTTPException(403, "forbidden")
    if not fp.exists() or not fp.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(fp)
