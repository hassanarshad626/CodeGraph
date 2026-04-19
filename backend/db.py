import json
import sqlite3
import threading
from pathlib import Path
from typing import Iterable

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS changes (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts    TEXT    NOT NULL,
    path  TEXT    NOT NULL,
    kind  TEXT    NOT NULL,
    size  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_changes_ts ON changes(ts DESC);

CREATE TABLE IF NOT EXISTS nodes (
    id    TEXT PRIMARY KEY,
    kind  TEXT NOT NULL,
    name  TEXT NOT NULL,
    path  TEXT NOT NULL,
    line  INTEGER,
    meta  TEXT
);
CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);

CREATE TABLE IF NOT EXISTS edges (
    src   TEXT NOT NULL,
    dst   TEXT NOT NULL,
    kind  TEXT NOT NULL,
    PRIMARY KEY (src, dst, kind)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
"""


class Store:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with _LOCK:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def log_change(self, ts: str, path: str, kind: str, size: int | None):
        with _LOCK:
            self._conn.execute(
                "INSERT INTO changes(ts, path, kind, size) VALUES (?,?,?,?)",
                (ts, path, kind, size),
            )
            self._conn.commit()

    def recent_changes(self, limit: int = 100) -> list[dict]:
        with _LOCK:
            rows = self._conn.execute(
                "SELECT ts, path, kind, size FROM changes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def replace_file_nodes(self, path: str, nodes: list[dict], edges: list[dict]):
        """Atomically replace all nodes/edges originating from `path`."""
        with _LOCK:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id FROM nodes WHERE path = ?",
                (path,),
            )
            old_ids = [r["id"] for r in cur.fetchall()]
            if old_ids:
                placeholders = ",".join("?" * len(old_ids))
                cur.execute(f"DELETE FROM edges WHERE src IN ({placeholders}) OR dst IN ({placeholders})", old_ids * 2)
                cur.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", old_ids)
            for n in nodes:
                cur.execute(
                    "INSERT OR REPLACE INTO nodes(id, kind, name, path, line, meta) VALUES (?,?,?,?,?,?)",
                    (n["id"], n["kind"], n["name"], n["path"], n.get("line"), json.dumps(n.get("meta", {}))),
                )
            for e in edges:
                cur.execute(
                    "INSERT OR IGNORE INTO edges(src, dst, kind) VALUES (?,?,?)",
                    (e["src"], e["dst"], e["kind"]),
                )
            self._conn.commit()

    def delete_file(self, path: str):
        with _LOCK:
            cur = self._conn.cursor()
            cur.execute("SELECT id FROM nodes WHERE path = ?", (path,))
            ids = [r["id"] for r in cur.fetchall()]
            if ids:
                placeholders = ",".join("?" * len(ids))
                cur.execute(f"DELETE FROM edges WHERE src IN ({placeholders}) OR dst IN ({placeholders})", ids * 2)
                cur.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", ids)
            self._conn.commit()

    def all_nodes(self) -> list[dict]:
        with _LOCK:
            rows = self._conn.execute("SELECT id, kind, name, path, line FROM nodes").fetchall()
        return [dict(r) for r in rows]

    def all_edges(self) -> list[dict]:
        with _LOCK:
            rows = self._conn.execute("SELECT src, dst, kind FROM edges").fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with _LOCK:
            counts = dict(
                self._conn.execute(
                    "SELECT kind, COUNT(*) AS c FROM nodes GROUP BY kind"
                ).fetchall()
            )
            total = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            file_exts = dict(
                self._conn.execute(
                    "SELECT json_extract(meta, '$.ext') AS ext, COUNT(*) AS c "
                    "FROM nodes WHERE kind='file' GROUP BY ext"
                ).fetchall()
            )
        return {"by_kind": counts, "total": total, "file_exts": file_exts}

    def close(self):
        with _LOCK:
            self._conn.close()
