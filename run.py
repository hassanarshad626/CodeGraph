"""Entry point: launches CodeGraph at http://localhost:8765"""
import os
import threading
import time
import webbrowser

import uvicorn

PORT = 8765


def _open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    if not os.environ.get("CODEGRAPH_NO_BROWSER"):
        threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=PORT, reload=False)
