"""FastAPI app entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from app.config import settings
from app.routes import projects, clips, render, files, settings as settings_route

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"storage at {settings.storage_path}")
    logger.info(f"CORS allowed: {settings.cors_list}")
    yield

app = FastAPI(title="mpt-editor", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(clips.router)
app.include_router(render.router)
app.include_router(files.router)
app.include_router(settings_route.router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.GEMINI_MODEL}
