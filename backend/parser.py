"""Lightweight code parsers: Python via ast, JS/TS via regex.

Returns (nodes, edges) for a single file. The caller persists them.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PY_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SUPPORTED_EXTS = PY_EXTS | JS_EXTS


def file_node_id(rel_path: str) -> str:
    return f"file::{rel_path}"


def symbol_id(rel_path: str, name: str, kind: str) -> str:
    return f"{kind}::{rel_path}::{name}"


def import_id(module: str) -> str:
    return f"import::{module}"


def parse_file(abs_path: Path, rel_path: str) -> tuple[list[dict], list[dict]]:
    ext = abs_path.suffix.lower()
    file_nid = file_node_id(rel_path)
    nodes: list[dict] = [
        {
            "id": file_nid,
            "kind": "file",
            "name": abs_path.name,
            "path": rel_path,
            "line": 1,
            "meta": {"ext": ext},
        }
    ]
    edges: list[dict] = []

    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return nodes, edges

    if ext in PY_EXTS:
        _parse_python(text, rel_path, file_nid, nodes, edges)
    elif ext in JS_EXTS:
        _parse_js(text, rel_path, file_nid, nodes, edges)

    return nodes, edges


def _parse_python(text: str, rel_path: str, file_nid: str, nodes: list, edges: list):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nid = symbol_id(rel_path, node.name, "function")
            nodes.append({"id": nid, "kind": "function", "name": node.name,
                          "path": rel_path, "line": node.lineno, "meta": {}})
            edges.append({"src": file_nid, "dst": nid, "kind": "contains"})
        elif isinstance(node, ast.ClassDef):
            nid = symbol_id(rel_path, node.name, "class")
            nodes.append({"id": nid, "kind": "class", "name": node.name,
                          "path": rel_path, "line": node.lineno, "meta": {}})
            edges.append({"src": file_nid, "dst": nid, "kind": "contains"})
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mid = symbol_id(rel_path, f"{node.name}.{child.name}", "function")
                    nodes.append({"id": mid, "kind": "function", "name": f"{node.name}.{child.name}",
                                  "path": rel_path, "line": child.lineno, "meta": {}})
                    edges.append({"src": nid, "dst": mid, "kind": "contains"})
        elif isinstance(node, ast.Import):
            for n in node.names:
                iid = import_id(n.name)
                nodes.append({"id": iid, "kind": "import", "name": n.name,
                              "path": rel_path, "line": node.lineno, "meta": {}})
                edges.append({"src": file_nid, "dst": iid, "kind": "imports"})
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            iid = import_id(mod)
            nodes.append({"id": iid, "kind": "import", "name": mod,
                          "path": rel_path, "line": node.lineno, "meta": {}})
            edges.append({"src": file_nid, "dst": iid, "kind": "imports"})


_JS_FUNC = re.compile(
    r"""(?:^|\s)
        (?:export\s+)?(?:async\s+)?
        (?:function\s+(?P<f1>[A-Za-z_$][\w$]*)\s*\(
        |const\s+(?P<f2>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>
        |const\s+(?P<f3>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\b)
    """,
    re.VERBOSE | re.MULTILINE,
)
_JS_CLASS = re.compile(r"(?:^|\s)(?:export\s+)?class\s+(?P<c>[A-Za-z_$][\w$]*)", re.MULTILINE)
_JS_IMPORT = re.compile(
    r"""(?:^|\s)(?:import\s+(?:[^'";]+\s+from\s+)?['"](?P<m1>[^'"]+)['"]
        |require\(\s*['"](?P<m2>[^'"]+)['"]\s*\))
    """,
    re.VERBOSE | re.MULTILINE,
)


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _parse_js(text: str, rel_path: str, file_nid: str, nodes: list, edges: list):
    seen: set[str] = set()
    for m in _JS_FUNC.finditer(text):
        name = m.group("f1") or m.group("f2") or m.group("f3")
        if not name:
            continue
        nid = symbol_id(rel_path, name, "function")
        if nid in seen:
            continue
        seen.add(nid)
        nodes.append({"id": nid, "kind": "function", "name": name,
                      "path": rel_path, "line": _line_of(text, m.start()), "meta": {}})
        edges.append({"src": file_nid, "dst": nid, "kind": "contains"})
    for m in _JS_CLASS.finditer(text):
        name = m.group("c")
        nid = symbol_id(rel_path, name, "class")
        if nid in seen:
            continue
        seen.add(nid)
        nodes.append({"id": nid, "kind": "class", "name": name,
                      "path": rel_path, "line": _line_of(text, m.start()), "meta": {}})
        edges.append({"src": file_nid, "dst": nid, "kind": "contains"})
    for m in _JS_IMPORT.finditer(text):
        mod = m.group("m1") or m.group("m2")
        if not mod:
            continue
        iid = import_id(mod)
        nodes.append({"id": iid, "kind": "import", "name": mod,
                      "path": rel_path, "line": _line_of(text, m.start()), "meta": {}})
        edges.append({"src": file_nid, "dst": iid, "kind": "imports"})
