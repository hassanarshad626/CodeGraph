"""CodeGraph MCP server — exposes the live code graph to Claude Code.

Runs as a stdio MCP server and proxies to the local FastAPI backend at
http://localhost:8765. Add to Claude Code's MCP config:

  {
    "mcpServers": {
      "codegraph": {
        "command": "python",
        "args": ["D:/CodeGraph/mcp_server.py"]
      }
    }
  }

Requires:  pip install mcp httpx
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

BACKEND = os.environ.get("CODEGRAPH_BACKEND", "http://127.0.0.1:8765")

app = Server("codegraph")


async def _get(path: str, **params) -> Any:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{BACKEND}{path}", params=params)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        return r.json() if "application/json" in ct else r.text


async def _post(path: str, body: dict) -> Any:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.post(f"{BACKEND}{path}", json=body)
        r.raise_for_status()
        return r.json()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_projects",
            description="List all folders CodeGraph is currently watching.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_context",
            description="Return the full CONTEXT.md of the currently active project "
                        "(summary of files, classes, functions, imports, recent changes).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_graph",
            description="Return the active project's code graph as nodes and edges. "
                        "Nodes have kind ∈ {file, class, function, import}. "
                        "Edges have kind ∈ {contains, imports}.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="find_symbol",
            description="Search the active project's graph for symbols (functions, "
                        "classes, files, imports) whose name contains the query. "
                        "Case-insensitive substring match.",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Substring to match"},
                    "kind": {
                        "type": "string",
                        "enum": ["file", "class", "function", "import"],
                        "description": "Optional filter by node kind",
                    },
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="recent_changes",
            description="Return the active project's most recent file changes.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 25}},
            },
        ),
        Tool(
            name="select_project",
            description="Switch which watched folder is the 'active' one. "
                        "Other tools operate on the active project.",
            inputSchema={
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
        ),
        Tool(
            name="watch_project",
            description="Start watching a new folder (absolute path). "
                        "Also selects it as active.",
            inputSchema={
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
        ),
    ]


def _text(obj: Any) -> list[TextContent]:
    if isinstance(obj, str):
        return [TextContent(type="text", text=obj)]
    return [TextContent(type="text", text=json.dumps(obj, indent=2, default=str))]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "list_projects":
            return _text(await _get("/api/status"))

        if name == "get_context":
            return _text(await _get("/api/context"))

        if name == "get_graph":
            return _text(await _get("/api/graph"))

        if name == "find_symbol":
            g = await _get("/api/graph")
            q = (arguments.get("query") or "").lower()
            kind = arguments.get("kind")
            limit = int(arguments.get("limit", 50))
            matches = [
                n for n in g["nodes"]
                if q in (n.get("name") or "").lower()
                and (kind is None or n.get("kind") == kind)
            ][:limit]
            return _text({"count": len(matches), "matches": matches})

        if name == "recent_changes":
            limit = int(arguments.get("limit", 25))
            return _text(await _get("/api/changes", limit=limit))

        if name == "select_project":
            return _text(await _post("/api/select", {"path": arguments["path"]}))

        if name == "watch_project":
            return _text(await _post("/api/watch", {"path": arguments["path"]}))

        return _text(f"Unknown tool: {name}")
    except httpx.HTTPError as e:
        return _text(
            f"CodeGraph backend unreachable at {BACKEND}. "
            f"Start it with `python run.py`. ({e})"
        )


async def main():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
