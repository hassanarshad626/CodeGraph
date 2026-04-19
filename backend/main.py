"""FastAPI app: REST endpoints + serves the static frontend.

Multi-folder model: any number of folders can be watched simultaneously.
Each has its own SQLite store + watcher thread. The frontend picks one
"active" project to display in the graph view; the others keep their
CONTEXT.md / CLAUDE.md / AGENTS.md updated in the background.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import watcher as watcher_mod
from .db import Store
from .settings import Settings
from .watcher import WatchedProject

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend"
STATE_FILE = DATA_DIR / "state.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

app = FastAPI(title="CodeGraph")
settings = Settings(SETTINGS_FILE)


class Project:
    __slots__ = ("path", "store", "watcher")

    def __init__(self, path: Path, store: Store, watcher: WatchedProject):
        self.path = path
        self.store = store
        self.watcher = watcher


_projects: dict[str, Project] = {}
_active: Optional[str] = None


def _slug(p: Path) -> str:
    h = hashlib.sha1(str(p.resolve()).encode("utf-8")).hexdigest()[:10]
    return f"{p.name}-{h}"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"watched": [], "active": None}


def _save_state():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"watched": list(_projects.keys()), "active": _active}, indent=2),
        encoding="utf-8",
    )


def _start_watching(folder: Path) -> Project:
    folder = folder.resolve()
    key = str(folder)
    if key in _projects:
        return _projects[key]
    db_path = DATA_DIR / f"{_slug(folder)}.db"
    store = Store(db_path)
    watcher = WatchedProject(folder, store)
    watcher.start()
    proj = Project(folder, store, watcher)
    _projects[key] = proj
    return proj


def _stop_watching(key: str):
    proj = _projects.pop(key, None)
    if not proj:
        return
    proj.watcher.stop()
    proj.store.close()


def _get_active() -> Optional[Project]:
    if _active and _active in _projects:
        return _projects[_active]
    return None


# ---------- models ----------
class WatchRequest(BaseModel):
    path: str


class SelectRequest(BaseModel):
    path: str


class OpenRequest(BaseModel):
    path: str  # relative to the active project root
    line: int | None = None


# ---------- API ----------
@app.get("/api/status")
def status():
    return {
        "active": _active,
        "projects": [
            {"path": k, "name": Path(k).name}
            for k in _projects.keys()
        ],
    }


@app.post("/api/watch")
def watch(req: WatchRequest):
    global _active
    folder = Path(req.path).expanduser()
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(400, f"Not a directory: {folder}")
    proj = _start_watching(folder)
    _active = str(proj.path)
    _save_state()
    return {"ok": True, "active": _active}


@app.post("/api/unwatch")
def unwatch(req: WatchRequest):
    global _active
    key = str(Path(req.path).expanduser().resolve())
    _stop_watching(key)
    if _active == key:
        _active = next(iter(_projects.keys()), None)
    _save_state()
    return {"ok": True, "active": _active}


@app.post("/api/select")
def select(req: SelectRequest):
    global _active
    key = str(Path(req.path).expanduser().resolve())
    if key not in _projects:
        raise HTTPException(404, "Not watching that folder")
    _active = key
    _save_state()
    return {"ok": True, "active": _active}


@app.get("/api/graph")
def graph():
    p = _get_active()
    if not p:
        return {"nodes": [], "edges": []}
    return {"nodes": p.store.all_nodes(), "edges": p.store.all_edges()}


@app.get("/api/changes")
def changes(limit: int = 100):
    p = _get_active()
    if not p:
        return []
    return p.store.recent_changes(limit=limit)


@app.get("/api/context", response_class=PlainTextResponse)
def context():
    p = _get_active()
    if not p:
        return ""
    f = p.path / "CONTEXT.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


@app.get("/api/stats")
def stats():
    p = _get_active()
    if not p:
        return {"by_kind": {}, "total": 0, "file_exts": {}}
    return p.store.stats()


@app.get("/api/activity")
def activity():
    """Map of relative-path -> most-recent-change timestamp (ISO).
    Used by the frontend to draw a heatmap on the graph."""
    p = _get_active()
    if not p:
        return {}
    out: dict[str, str] = {}
    for c in p.store.recent_changes(limit=500):
        out.setdefault(c["path"], c["ts"])
    return out


@app.post("/api/open")
def open_file(req: OpenRequest):
    """Open a file at `path:line` in the user's editor.

    Priority: settings.editor_command → $CODEGRAPH_EDITOR env →
    VS Code on PATH → OS default handler.
    """
    p = _get_active()
    if not p:
        raise HTTPException(400, "No active project")
    full = (p.path / req.path).resolve()
    try:
        full.relative_to(p.path)
    except ValueError:
        raise HTTPException(400, "Path escapes project root")
    if not full.exists():
        raise HTTPException(404, f"Not found: {full}")
    line = req.line or 1
    target = f"{full}:{line}"

    custom = (settings.get("editor_command") or "").strip() \
        or os.environ.get("CODEGRAPH_EDITOR", "")
    try:
        if custom:
            cmd = custom.format(file=str(full), line=line, target=target)
            subprocess.Popen(cmd, shell=True)
            return {"ok": True, "opened_with": "custom"}

        code = shutil.which("code") or shutil.which("code.cmd")
        if code:
            subprocess.Popen([code, "--goto", target], shell=False)
            return {"ok": True, "opened_with": "vscode"}

        if sys.platform.startswith("win"):
            os.startfile(str(full))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(full)])
        else:
            subprocess.Popen(["xdg-open", str(full)])
        return {"ok": True, "opened_with": "default"}
    except Exception as e:
        raise HTTPException(500, f"Failed to open: {e}")


# ---------- settings ----------
@app.get("/api/settings")
def get_settings():
    return settings.all()


@app.post("/api/settings")
def set_settings(patch: dict):
    out = settings.update(patch)
    _apply_settings(out)
    return out


def _apply_settings(s: dict):
    extras = s.get("extra_ignore_dirs") or []
    if isinstance(extras, str):
        extras = [x.strip() for x in extras.split(",") if x.strip()]
    watcher_mod.EXTRA_IGNORE_DIRS = set(extras)


# ---------- static frontend ----------
_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html", headers=_NO_CACHE)


@app.middleware("http")
async def _no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        for k, v in _NO_CACHE.items():
            response.headers[k] = v
    return response


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.on_event("startup")
def _startup():
    global _active
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _apply_settings(settings.all())
    state = _load_state()
    for path in state.get("watched", []):
        try:
            _start_watching(Path(path))
        except Exception:
            pass
    saved_active = state.get("active")
    if saved_active and saved_active in _projects:
        _active = saved_active
    elif _projects:
        _active = next(iter(_projects.keys()))


@app.on_event("shutdown")
def _shutdown():
    for key in list(_projects.keys()):
        _stop_watching(key)
