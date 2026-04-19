"""User preferences persisted to data/settings.json.

Simple JSON-backed dict with sane defaults. Hot-reloaded by callers.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

DEFAULTS: dict[str, Any] = {
    # Editor command template. Placeholders: {file}, {line}.
    # Empty = auto-detect (VS Code if on PATH, else OS default).
    "editor_command": "",
    # Extra directories to ignore (merged with the built-in list).
    "extra_ignore_dirs": [],
    # How many minutes a file node stays "hot" in the heatmap after edit.
    "heatmap_minutes": 5,
    # Whether Electron should launch on login. Applied by the Electron app.
    "autostart": False,
    # Port (future — currently hardcoded; surfaced for forward-compat).
    "port": 8765,
    # UI preferences
    "enable_bobbing": True,
}


class Settings:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self):
        with _LOCK:
            if self.path.exists():
                try:
                    self._data = json.loads(self.path.read_text(encoding="utf-8"))
                except Exception:
                    self._data = {}
            else:
                self._data = {}

    def all(self) -> dict[str, Any]:
        with _LOCK:
            return {**DEFAULTS, **self._data}

    def get(self, key: str) -> Any:
        with _LOCK:
            return self._data.get(key, DEFAULTS.get(key))

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        with _LOCK:
            # Only accept known keys.
            for k, v in patch.items():
                if k in DEFAULTS:
                    self._data[k] = v
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )
            return {**DEFAULTS, **self._data}
