#!/usr/bin/env python3
"""Shared Engraphis client for the engraphis-memory catcode plugin.

Talks to a local self-hosted Engraphis server (see ~/engraphis;
`engraphis-update` to maintain it). Provides:

  - config()        env-driven configuration (URL, workspace, token)
  - api()           HTTP client (stdlib urllib, no deps) with timeouts
  - fmt_mem()       one-line memory formatter for display
  - resolve_*()     scope mapping between catcode and Engraphis
  - read_ctx()      read the stdin JSON context (works for both the
                    memory_provider contract and the tool contract)
  - emit()          write a single JSON object to stdout
  - ServerDown      exception raised when the server is unreachable

All tool/provider scripts import this module via a sys.path shim:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))

Configure (env, all optional — loopback single-user needs none):
  ENGRAPHIS_URL             http://127.0.0.1:8700
  ENGRAPHIS_WORKSPACE       "default"   (top-level scope)
  ENGRAPHIS_GLOBAL_WS        "global"   (scope used for catcode `global` memories)
  ENGRAPHIS_API_TOKEN        ""          (bearer token, only if the server sets one)
  ENGRAPHIS_DEFAULT_IMPORTANCE 0.0       (salience 0..1 for auto-saved memories)

Tools degrade gracefully: if the server is unreachable, writes return ok:false
with an actionable hint and inject returns an empty injection (soft).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# cwd basenames that are NOT real project repos — don't auto-scope to these.
_JUNK_REPOS = {
    "tmp", "temp", "root", "home", "var", "usr", "etc", "opt", "srv", "mnt",
    "media", "bin", "sbin", "lib", "lib64", "proc", "sys", "dev", "run",
    "boot", "snap", "workspace", "repo", "code", "src", "project",
}


class ServerDown(Exception):
    """Raised when the Engraphis server is unreachable."""


class ApiError(Exception):
    """Raised when the server responds with an error (non-2xx or bad JSON)."""


def config() -> dict[str, str]:
    base = os.environ.get("ENGRAPHIS_URL", "http://127.0.0.1:8700").rstrip("/")
    return {
        "base": base,
        "default_ws": os.environ.get("ENGRAPHIS_WORKSPACE", "default"),
        "global_ws": os.environ.get("ENGRAPHIS_GLOBAL_WS", "global"),
        "token": os.environ.get("ENGRAPHIS_API_TOKEN", ""),
        "default_importance": os.environ.get("ENGRAPHIS_DEFAULT_IMPORTANCE", "0.0"),
    }


def _auth_headers(cfg: dict[str, str]) -> dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if cfg["token"]:
        h["Authorization"] = f"Bearer {cfg['token']}"
    return h


def api(
    path: str,
    method: str = "GET",
    body: Any = None,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> Any:
    """Call the Engraphis server. Returns parsed JSON (or None for empty body).

    Raises ServerDown on connection failure, ApiError on HTTP/parse errors.
    """
    cfg = config()
    url = cfg["base"] + path
    if params:
        qs = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
        if qs:
            url += ("&" if "?" in url else "?") + qs

    data = None
    headers = _auth_headers(cfg)
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        msg = raw
        try:
            j = json.loads(raw) if raw else None
            if j:
                d = j.get("detail")
                if isinstance(d, dict):
                    msg = d.get("error") or d.get("message") or str(d)
                elif d:
                    msg = str(d)
                else:
                    msg = j.get("error") or j.get("message") or raw
        except (ValueError, TypeError):
            pass
        raise ApiError(f"HTTP {e.code}: {msg}" if msg else f"HTTP {e.code}")
    except urllib.error.URLError as e:
        # Connection refused / DNS / timeout — server is down.
        raise ServerDown(f"{cfg['base']} ({e.reason})")
    except TimeoutError as e:
        raise ServerDown(f"{cfg['base']} (timeout: {e})")

    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def pct(score: Any) -> str:
    if score is None:
        return ""
    try:
        n = float(score)
    except (TypeError, ValueError):
        return ""
    if n > 1:
        n = n / 5.0  # server scores on a 0..5 scale sometimes
    return f" ({round(min(max(n, 0.0), 1.0) * 100)}%)"


def fmt_mem(m: dict[str, Any]) -> str:
    """Format a memory object as a bulleted one-liner (+ truncated content)."""
    pin = " 📌" if m.get("pinned") else ""
    mtype = m.get("memory_type") or m.get("mtype") or ""
    ws = f" [{m['_workspace']}]" if m.get("_workspace") else ""
    score = pct(m.get("score"))
    title = m.get("title") or "(untitled)"
    content = str(m.get("content") or "").replace("\n", " ").strip()
    if len(content) > 400:
        content = content[:397] + "..."
    mid = m.get("id", "?")
    line = f"- [{mid}] {title}{pin}"
    if mtype:
        line += f" <{mtype}>"
    line += f"{ws}{score}"
    if content:
        line += f"\n    {content}"
    return line


def repo_of(workspace_path: str | None) -> str | None:
    """Derive a repo scope from the workspace path's basename."""
    if not workspace_path:
        return None
    base = os.path.basename(workspace_path.rstrip("/"))
    if base and base != "." and base.lower() not in _JUNK_REPOS:
        return base
    return None


def resolve_scope(scope: str | None, workspace_path: str | None) -> tuple[str, str | None]:
    """Map a catcode memory scope to an Engraphis (workspace, repo) pair.

    catcode `workspace` (per-codebase) → Engraphis workspace=default, repo=basename.
    catcode `global` (cross-codebase)   → Engraphis workspace=global,  repo=None.
    """
    cfg = config()
    if scope == "global":
        return (cfg["global_ws"], None)
    # default "workspace" scope
    return (cfg["default_ws"], repo_of(workspace_path))


def resolve_tool_scope(
    args: dict[str, Any], workspace_path: str | None
) -> tuple[str, str | None]:
    """Resolve (workspace, repo) for a TOOL call.

    Tools expose Engraphis's native `workspace` and `repo` params (like the PI
    plugin): workspace defaults to the default_ws; repo defaults to the cwd
    basename. Either may be overridden by the caller.
    """
    cfg = config()
    ws = args.get("workspace") or cfg["default_ws"]
    repo = args.get("repo")
    if not repo:
        repo = repo_of(workspace_path)
    return (ws, repo)


def read_ctx() -> dict[str, Any]:
    """Read the stdin JSON context. Tolerant: returns {} on parse failure."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def emit(obj: dict[str, Any]) -> None:
    """Write a single JSON object to stdout and flush."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


def server_hint() -> str:
    """An actionable hint shown when the server is unreachable."""
    cfg = config()
    return (
        f"Engraphis server unreachable at {cfg['base']}. "
        "Start it (e.g. `cd ~/engraphis && engraphis-update` or run the server), "
        "or set ENGRAPHIS_URL to point at it. Memories will persist once it is up."
    )
