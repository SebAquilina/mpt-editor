"""Project lifecycle endpoints."""
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sse_starlette.sse import EventSourceResponse
from app.models.schema import (
    CreateProjectRequest, CreateProjectResponse, Project,
)
from app.storage import db
from app.services.pipeline import run_pipeline
from app.services.events import events

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.post("", response_model=CreateProjectResponse)
async def create_project(body: CreateProjectRequest, background: BackgroundTasks):
    project = Project(prompt=body.prompt, status="queued")
    db.save(project)
    background.add_task(run_pipeline, project.id)
    return CreateProjectResponse(project_id=project.id)

@router.get("", response_model=list[Project])
async def list_projects():
    return db.list_all()

@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str):
    p = db.load(project_id)
    if not p:
        raise HTTPException(404, "project not found")
    return p

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    if not db.delete(project_id):
        raise HTTPException(404, "project not found")
    return {"ok": True}

@router.get("/{project_id}/events")
async def stream_events(project_id: str):
    p = db.load(project_id)
    if not p:
        raise HTTPException(404, "project not found")
    async def gen():
        # initial snapshot
        yield {"event": "snapshot", "data": json.dumps({"status": p.status, "progress": p.progress, "message": p.progress_message})}
        async for ev in events.stream(project_id):
            yield {"event": ev.get("type", "message"), "data": json.dumps(ev)}
    return EventSourceResponse(gen())
