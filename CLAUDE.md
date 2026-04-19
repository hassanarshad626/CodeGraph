<!-- BEGIN CodeGraph auto-generated -->
# Agent instructions

The full live project context is below (mirrored from `CONTEXT.md`). Treat it as
authoritative for the current shape of the codebase. It is regenerated on every
file change by the CodeGraph watcher.

---

# Project Context — auto-generated
_Last updated: 2026-04-19 11:48:53_

Agents (Claude Code, Antigravity, Cursor, Codex, etc.): **read this file first**.
It reflects the live state of the project, refreshed on every file save.

## Stats

- Total graph nodes: **218**
- Files: 15
- Classes: 8
- Functions: 154
- Imports: 41
- File types: `.js`×3, `.py`×12

## Recent changes (last 25)

- `2026-04-19 11:47:19`  **modified**  `frontend/app.js`
- `2026-04-19 11:47:14`  **modified**  `frontend/app.js`
- `2026-04-19 11:47:10`  **modified**  `frontend/app.js`
- `2026-04-19 11:47:00`  **modified**  `frontend/style.css`
- `2026-04-19 11:46:52`  **modified**  `frontend/index.html`
- `2026-04-19 11:46:40`  **modified**  `frontend/index.html`
- `2026-04-19 11:46:36`  **modified**  `backend/main.py`
- `2026-04-19 11:46:31`  **modified**  `backend/main.py`
- `2026-04-19 11:46:22`  **modified**  `backend/main.py`
- `2026-04-19 11:46:18`  **modified**  `backend/watcher.py`
- `2026-04-19 11:46:14`  **modified**  `backend/watcher.py`
- `2026-04-19 11:46:08`  **modified**  `backend/main.py`
- `2026-04-19 11:46:03`  **modified**  `backend/main.py`
- `2026-04-19 11:45:54`  **modified**  `backend/main.py`
- `2026-04-19 11:45:49`  **modified**  `backend/main.py`
- `2026-04-19 11:45:46`  **modified**  `backend/settings.py`
- `2026-04-19 11:45:34`  **modified**  `electron/main.js`
- `2026-04-19 11:45:28`  **modified**  `electron/main.js`
- `2026-04-19 11:45:22`  **modified**  `electron/icon.ico`
- `2026-04-19 11:45:22`  **modified**  `electron/icon_tray.png`
- `2026-04-19 11:45:22`  **modified**  `electron/icon.png`
- `2026-04-19 11:45:12`  **modified**  `scripts/make_icons.py`
- `2026-04-19 11:44:26`  **modified**  `backend/context.py`
- `2026-04-19 11:40:42`  **modified**  `frontend/app.js`
- `2026-04-19 11:40:37`  **modified**  `frontend/app.js`

## Files

### `backend/__init__.py`

### `backend/context.py`
- **Functions:** _build_context, _git_section, _merge_into, _wrap, _write_or_merge, write_all
- **Imports:** __future__, datetime, db, git_info, pathlib

### `backend/db.py`
- **Classes:** Store
- **Functions:** __init__, all_edges, all_nodes, close, delete_file, log_change, recent_changes, replace_file_nodes, stats
- **Imports:** json, pathlib, sqlite3, threading, typing

### `backend/git_info.py`
- **Functions:** _run, get_git_info
- **Imports:** __future__, pathlib, subprocess

### `backend/main.py`
- **Classes:** OpenRequest, Project, SelectRequest, WatchRequest
- **Functions:** __init__, _apply_settings, _get_active, _load_state, _no_cache_static, _save_state, _shutdown, _slug, _start_watching, _startup, _stop_watching, activity, changes, context, get_settings, graph, index, open_file, select, set_settings, stats, status, unwatch, watch
- **Imports:** , __future__, db, fastapi, fastapi.responses, fastapi.staticfiles, hashlib, json, os, pathlib, pydantic, settings, shutil, subprocess, sys, typing, watcher

### `backend/parser.py`
- **Functions:** _line_of, _parse_js, _parse_python, file_node_id, import_id, parse_file, symbol_id
- **Imports:** __future__, ast, pathlib, re

### `backend/settings.py`
- **Classes:** Settings
- **Functions:** __init__, _load, all, get, update
- **Imports:** __future__, json, pathlib, threading, typing

### `backend/watcher.py`
- **Classes:** WatchedProject, _Handler
- **Functions:** __init__, _flush, _initial_scan, _is_ignored, _reparse, enqueue, on_created, on_deleted, on_modified, on_moved, start, stop
- **Imports:** , __future__, datetime, db, parser, pathlib, threading, time, watchdog.events, watchdog.observers

### `build.py`
- **Functions:** main
- **Imports:** PyInstaller, __future__, pathlib, shutil, subprocess, sys

### `electron/main.js`
- **Functions:** createTray, createWindow, resolveBackend, startBackend, stopBackend, tryOnce, waitForBackend
- **Imports:** child_process, electron, http, path

### `electron/preload.js`
- **Imports:** electron

### `frontend/app.js`
- **Functions:** $, api, applyHeatmap, applyKindFilter, bindModals, bindUI, buildHandoffPrompt, buildSuggestions, captureBasePositions, clearSelection, closeModal, doPick, doWatch, escapeHtml, frame, hoverClear, hoverHighlight, initCy, layoutOpts, mkList, openHandoff, openInEditor, openModal, openSettings, refreshActivity, refreshChanges, refreshContext, refreshGraph, refreshStats, refreshStatus, regen, runLayout, saveSettings, selectNode, shortLabel, showTooltip, startBobbing, startDashFlow, startPulse, stopBobbing, tick, updateEmptyHint

### `mcp_server.py`
- **Functions:** _get, _post, _text, call_tool, list_tools, main
- **Imports:** __future__, asyncio, httpx, json, mcp.server, mcp.server.stdio, mcp.types, os, typing

### `run.py`
- **Functions:** _open_browser
- **Imports:** os, threading, time, uvicorn, webbrowser

### `scripts/make_icons.py`
- **Functions:** _hexagon, _with_glow, main, make_png
- **Imports:** PIL, __future__, math, pathlib

<!-- END CodeGraph auto-generated -->
