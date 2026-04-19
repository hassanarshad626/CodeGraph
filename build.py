"""Build a standalone CodeGraph backend executable.

Packages the Python backend + all dependencies into a single folder
(`dist/codegraph-backend/`) using PyInstaller. Electron's main.js looks
for this folder at runtime when no system Python is available.

Usage:
    pip install pyinstaller
    python build.py

Then inside the electron/ folder:
    npm run dist    # builds the installer (requires electron-builder config)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "run.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def main():
    if not ENTRY.exists():
        sys.exit(f"entry point not found: {ENTRY}")

    try:
        import PyInstaller  # noqa
    except ImportError:
        sys.exit("PyInstaller is not installed. Run: pip install pyinstaller")

    # Clean previous builds.
    for d in (DIST / "codegraph-backend", BUILD):
        if d.exists():
            shutil.rmtree(d)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", "codegraph-backend",
        "--onedir",           # folder mode is more reliable than --onefile
        "--console",
        "--paths", str(ROOT),
        "--add-data", f"{ROOT / 'frontend'}{';' if sys.platform.startswith('win') else ':'}frontend",
        # Hidden imports that PyInstaller's static analysis misses.
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "backend.main",
        "--hidden-import", "backend.watcher",
        "--hidden-import", "backend.parser",
        "--hidden-import", "backend.db",
        "--hidden-import", "backend.context",
        "--hidden-import", "backend.git_info",
        "--hidden-import", "backend.settings",
        str(ENTRY),
    ]
    print(">>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    out = DIST / "codegraph-backend"
    if not out.exists():
        sys.exit(f"build failed — {out} not produced")
    print(f"\nBuilt: {out}")
    print("Next: cd electron && npm run dist")


if __name__ == "__main__":
    main()
