# mpt-editor

Prompt-to-video editor with Gemini-assisted clip matching, built on top of MoneyPrinterTurbo.

The user types one prompt. The pipeline generates a script, runs TTS, searches YouTube + Pexels, has Gemini 3.5 Flash pick the best visual segment for each line, and lands the user in a **two-track timeline editor** where they can swap, delete, or reorder any clip and re-render.

## Architecture

```
┌─────────────────────────┐         ┌──────────────────────────┐
│  Frontend (React + TS)  │ <-----> │  Backend (FastAPI)       │
│  Two-track timeline UI  │   HTTP  │  + Gemini + yt-dlp +     │
│  Vite + Tailwind + dnd  │   SSE   │  EdgeTTS + ffmpeg        │
└─────────────────────────┘         └──────────────────────────┘
```

### Pipeline phases (per prompt)

1. **Script generation** — Gemini 3.5 Flash writes ~1,800 word script with 7-section structure.
2. **TTS** — EdgeTTS synthesizes per-paragraph audio chunks.
3. **Discovery** — YouTube via `yt-dlp ytsearch` (no API key) + Pexels API.
4. **Matching** — Gemini watches each candidate video, returns timestamp ranges with `match_quality`.
5. **Extraction** — `yt-dlp --download-sections` pulls only the chosen window.
6. **Normalization** — Every clip scaled to 1920×1080, audio stripped, attribution overlay burned in.
7. **Hybrid plan** — YouTube clips fill each paragraph first, Pexels fills remainder.
8. **Assembly** — ffmpeg concat + audio mux + BGM + subtitles + endcard.

### Editor capabilities

- **Two synchronized timeline tracks**: top = TTS waveform with script overlay per sentence; bottom = clip cards.
- **Delete a clip** → backend launches a fresh Gemini search for **3 alternates**; user picks one (or cancels).
- **Replace a clip** → drawer with three tabs:
  - **Leftovers** — pre-searched candidates we didn't use.
  - **Search** — live YouTube + Pexels search.
  - **Upload** — drag-drop your own MP4.
- **Drag-to-reorder** clips within a paragraph.
- **Render** → reassembled MP4 with all edits.

## Quick start

```bash
# 1) Backend
cd backend
uv sync --frozen
cp .env.example .env  # fill in GEMINI_API_KEY and PEXELS_API_KEY
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2) Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev  # http://localhost:5173
```

Requirements: Python 3.11+, Node 20+, ffmpeg on PATH, ~5 GB of free disk for project workspace.

## Environment variables

| Key | Required | What it's for |
|---|---|---|
| `GEMINI_API_KEY` | yes | Script generation, video matching, query generation |
| `PEXELS_API_KEY` | yes | Stock-footage fallback |
| `STORAGE_DIR` | no | Defaults to `./backend/data` |
| `BACKEND_HOST` | no | Defaults to `0.0.0.0:8000` |
| `CORS_ORIGINS` | no | Comma-separated, defaults to `http://localhost:5173` |

## Repo layout

```
mpt-editor/
├── backend/           # FastAPI + pipeline services
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/    # projects, clips, render, files
│   │   ├── services/  # pipeline, script, tts, youtube, pexels, render
│   │   └── models/    # pydantic schemas
│   └── pyproject.toml
├── frontend/          # Vite + React + TS + Tailwind
│   └── src/
│       ├── pages/     # Home, Generating, Editor
│       ├── components/  # Timeline, ScriptTrack, ClipTrack, drawers
│       └── api/
└── README.md
```

## License

MIT. See LICENSE.
