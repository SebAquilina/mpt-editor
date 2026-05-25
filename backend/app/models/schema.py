"""Pydantic schemas — the contract between backend and frontend."""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field
import uuid

ProjectStatus = Literal[
    "queued",            # created, pipeline not started
    "generating_script", # Gemini writing script
    "generating_tts",    # EdgeTTS
    "searching",         # YouTube + Pexels search
    "matching",          # Gemini timestamp matching
    "downloading",       # yt-dlp + Pexels downloads
    "normalizing",       # ffmpeg normalize
    "ready",             # editor-ready
    "rendering",         # rendering final video
    "rendered",          # final video ready
    "error",
]

ClipSource = Literal["youtube", "pexels", "upload"]

class ClipBase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: ClipSource
    file_path: str                          # relative to STORAGE_DIR
    thumbnail_path: str | None = None
    duration_sec: float
    paragraph_id: int
    order_in_paragraph: int
    visual_description: str | None = None
    match_quality: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # YouTube source metadata
    yt_video_id: str | None = None
    yt_channel: str | None = None
    yt_video_title: str | None = None
    yt_video_url: str | None = None
    yt_start_sec: float | None = None
    yt_end_sec: float | None = None

    # Pexels source metadata
    pexels_id: str | None = None
    pexels_url: str | None = None
    pexels_query: str | None = None

    # Upload metadata
    upload_filename: str | None = None

class Clip(ClipBase):
    pass

class Sentence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    start_sec: float                        # absolute timeline (full project)
    end_sec: float
    paragraph_id: int

class Paragraph(BaseModel):
    id: int                                 # 0..N
    text: str
    audio_path: str                         # per-paragraph TTS audio file (relative to STORAGE_DIR)
    audio_duration_sec: float
    timeline_start_sec: float               # absolute timeline offset
    sentences: list[Sentence] = []
    clips: list[Clip] = []
    search_queries: list[str] = []          # Gemini-generated queries used

class RenderRecord(BaseModel):
    """One completed (or in-flight) render of a project. Lets the editor keep a history."""
    id: str
    video_path: str | None = None
    duration_sec: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    status: Literal["pending", "rendering", "complete", "failed"] = "pending"
    error_message: str | None = None
    notes: str | None = None                # e.g. "after deleting clip P2_03"

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str
    title: str = ""
    status: ProjectStatus = "queued"
    progress: float = 0.0                   # 0..100
    progress_message: str = ""
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    full_audio_path: str | None = None
    full_subtitles_path: str | None = None
    final_video_path: str | None = None     # latest render — kept for backward-compat with the editor preview

    renders: list[RenderRecord] = []         # full render history (newest last)

    paragraphs: list[Paragraph] = []

    # Pre-searched candidates we didn't use, for the "Leftovers" tab
    youtube_leftovers: list[Clip] = []
    pexels_leftovers: list[Clip] = []

# ─── Request/response shapes ──────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    prompt: str
    voice: str | None = None

class CreateProjectResponse(BaseModel):
    project_id: str

class ReorderRequest(BaseModel):
    paragraph_id: int
    ordered_clip_ids: list[str]

class AlternatesRequest(BaseModel):
    """Request for delete-with-3-alternates: backend finds 3 fresh candidates."""
    pass

class AlternatesResponse(BaseModel):
    alternates: list[Clip]

class SearchClipRequest(BaseModel):
    query: str
    source: Literal["youtube", "pexels", "both"] = "both"

class SearchClipResponse(BaseModel):
    results: list[Clip]

class ReplaceClipRequest(BaseModel):
    new_clip_id: str                        # an alternate, leftover, search result, or upload

class RenderResponse(BaseModel):
    render_id: str
    video_url: str
