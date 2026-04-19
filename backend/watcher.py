"""File-system watcher: parses changed files and updates store + context files."""
from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import context as ctx_mod
from .db import Store
from .parser import SUPPORTED_EXTS, parse_file

# Populated by main.py at startup; kept as a module-level set so watchers
# pick up settings changes without restart.
EXTRA_IGNORE_DIRS: set[str] = set()

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build",
               ".idea", ".vscode", ".next", ".cache", "data", ".claude",
               ".DS_Store", ".pytest_cache", ".mypy_cache", "target", "out"}
IGNORE_FILES = {"CONTEXT.md", "CLAUDE.md", "AGENTS.md"}
IGNORE_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo", ".lock")
DEBOUNCE_SECONDS = 0.4


class WatchedProject:
    def __init__(self, folder: Path, store: Store):
        self.folder = folder.resolve()
        self.store = store
        self.observer: Observer | None = None
        self._pending: dict[str, str] = {}  # rel_path -> kind
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    # ---------- public API ----------
    def start(self):
        self._initial_scan()
        ctx_mod.write_all(self.folder, self.store)

        handler = _Handler(self)
        self.observer = Observer()
        self.observer.schedule(handler, str(self.folder), recursive=True)
        self.observer.start()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.observer = None

    # ---------- internal ----------
    def _is_ignored(self, abs_path: Path) -> bool:
        try:
            rel = abs_path.relative_to(self.folder)
        except ValueError:
            return True
        name = abs_path.name
        if name in IGNORE_FILES:
            return True
        if name.startswith("."):
            # Hidden files (editor backups, swap files, etc.)
            if name not in {".env", ".gitignore", ".dockerignore"}:
                return True
        # Atomic-write temp files (e.g. foo.py.tmp.1234.5678)
        if ".tmp." in name or name.endswith(".tmp"):
            return True
        if name.endswith(IGNORE_SUFFIXES):
            return True
        if name.endswith("~"):
            return True
        for part in rel.parts:
            if part in IGNORE_DIRS or part in EXTRA_IGNORE_DIRS:
                return True
            if part.startswith(".") and part != ".env":
                return True
        return False

    def _initial_scan(self):
        for path in self.folder.rglob("*"):
            if not path.is_file():
                continue
            if self._is_ignored(path):
                continue
            if path.suffix.lower() not in SUPPORTED_EXTS:
                # still record file existence for non-parsed extensions
                continue
            rel = str(path.relative_to(self.folder)).replace("\\", "/")
            self._reparse(path, rel)

    def _reparse(self, abs_path: Path, rel: str):
        try:
            nodes, edges = parse_file(abs_path, rel)
            self.store.replace_file_nodes(rel, nodes, edges)
        except Exception:
            pass

    def enqueue(self, abs_path: Path, kind: str):
        if self._is_ignored(abs_path):
            return
        try:
            rel = str(abs_path.resolve().relative_to(self.folder)).replace("\\", "/")
        except ValueError:
            return
        with self._lock:
            self._pending[rel] = kind
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self):
        with self._lock:
            pending = dict(self._pending)
            self._pending.clear()
        if not pending:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for rel, kind in pending.items():
            abs_path = self.folder / rel
            size = abs_path.stat().st_size if abs_path.exists() else None
            self.store.log_change(ts, rel, kind, size)
            if kind == "deleted":
                self.store.delete_file(rel)
            elif abs_path.suffix.lower() in SUPPORTED_EXTS and abs_path.exists():
                self._reparse(abs_path, rel)
        ctx_mod.write_all(self.folder, self.store)


class _Handler(FileSystemEventHandler):
    def __init__(self, project: WatchedProject):
        self.project = project

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self.project.enqueue(Path(event.src_path), "created")

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self.project.enqueue(Path(event.src_path), "modified")

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self.project.enqueue(Path(event.src_path), "deleted")

    def on_moved(self, event: FileSystemEvent):
        if not event.is_directory:
            self.project.enqueue(Path(event.dest_path), "modified")
            self.project.enqueue(Path(event.src_path), "deleted")
