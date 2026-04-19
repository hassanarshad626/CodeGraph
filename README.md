# CodeGraph

A local watcher + visualizer that keeps a live `CONTEXT.md` (plus `CLAUDE.md`
and `AGENTS.md`) in any folder you point it at, so multiple AI agents
(Claude Code, Antigravity, Cursor, Codex, …) can share the same up-to-date
project context without you re-pasting it every time.

## What it does

1. **Watch** any number of folders simultaneously. Every save re-parses changed files.
2. **Parse** Python (via `ast`) and JS/TS (via regex) into a graph of
   files → classes → functions → imports.
3. **Persist** to SQLite (one DB per watched folder, in `./data`).
4. **Auto-write** three files at each watched folder root on every change:
   - `CONTEXT.md` — human-readable project summary
   - `CLAUDE.md` — same content, auto-read by Claude Code
   - `AGENTS.md` — same content, auto-read by Antigravity / Cursor / Codex
5. **Visualize** the graph in a dark Neo4j-style UI — browser, Electron window, or both.
6. **MCP server** — lets Claude Code query the graph directly (not just read CONTEXT.md).

## Setup

### Option A: browser (simplest)

```
pip install -r requirements.txt
python run.py
```

Opens http://localhost:8765.

### Option B: Electron desktop app

```
pip install -r requirements.txt
cd electron
npm install
npm start
```

Native window + system tray + "Pick folder…" button using the OS folder dialog.
Close the window → it minimizes to the tray. Right-click tray → Quit.

## Hooking Claude Code up to the MCP server

Add this to `~/.claude/mcp_servers.json` (or your project's `.mcp.json`):

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "python",
      "args": ["D:/CodeGraph/mcp_server.py"]
    }
  }
}
```

Restart Claude Code. You'll get tools:
- `list_projects` — what's being watched
- `get_context` — full CONTEXT.md of active project
- `get_graph` — raw nodes + edges
- `find_symbol` — substring search across the graph
- `recent_changes` — change log
- `select_project` / `watch_project` — switch or add projects

The MCP server just proxies to the running FastAPI backend, so `python run.py`
(or the Electron app) must be running.

## How agents use it

When you point any agent at a watched folder:
- **Claude Code** auto-reads `CLAUDE.md` on session start
- **Antigravity / Cursor / Codex / Aider** auto-read `AGENTS.md`

Both files always mirror the live `CONTEXT.md`. Zero manual prompting.

## Preferences

Click the ⚙ icon in the top-right to open the preferences window. You can configure:

- **Editor command** — e.g. `code --goto {file}:{line}` (VS Code, default),
  `cursor {file}:{line}`, `idea --line {line} {file}` (JetBrains).
- **Extra ignore folders** — added to the built-in list on top of `.git`,
  `node_modules`, `__pycache__`, etc.
- **Heatmap duration** — how long a recently-edited file glows in the graph.
- **Autostart at login** — launches CodeGraph silently in the tray when you log in.
- **Animations** — toggle the gentle node bobbing.

Settings are saved to `data/settings.json`.

## Packaging (distribute as a single installer)

To produce a standalone installer that doesn't require Python or Node:

```
pip install pyinstaller
python build.py                       # → dist/codegraph-backend/
cd electron
npm install
npm run dist                          # → electron/dist/CodeGraph Setup *.exe
```

`electron-builder` picks up:
- the `dist/codegraph-backend/` folder produced by PyInstaller (becomes the
  bundled backend; no system Python needed)
- `electron/icon.ico` for the Windows installer & app icon
- `electron/icon.png` for macOS/Linux builds

Run `python scripts/make_icons.py` any time you want to regenerate the
hexagon logo icons.

## Notes
- Ignores `.git`, `node_modules`, `__pycache__`, `.venv`, build outputs.
- The three generated `.md` files are themselves ignored (no watch loop).
- All processing is local — nothing leaves your machine.
- Each project has its own SQLite DB; state survives restarts and auto-resumes watching.
