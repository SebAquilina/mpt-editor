"""JSON-file-backed project store. Single-user / single-machine — no DB needed."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading
from app.config import settings
from app.models.schema import Project

_lock = threading.Lock()

def _project_file(project_id: str) -> Path:
    return settings.storage_path / "projects" / f"{project_id}.json"

def save(project: Project) -> None:
    with _lock:
        project.updated_at = datetime.utcnow()
        path = _project_file(project.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(project.model_dump_json(indent=2))

def load(project_id: str) -> Optional[Project]:
    path = _project_file(project_id)
    if not path.exists():
        return None
    return Project.model_validate_json(path.read_text())

def list_all() -> list[Project]:
    projects = []
    pd = settings.storage_path / "projects"
    if not pd.exists():
        return projects
    for f in sorted(pd.glob("*.json")):
        try:
            projects.append(Project.model_validate_json(f.read_text()))
        except Exception:
            continue
    return projects

def delete(project_id: str) -> bool:
    path = _project_file(project_id)
    if path.exists():
        path.unlink()
        return True
    return False
