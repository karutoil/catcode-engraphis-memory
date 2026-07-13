#!/usr/bin/env python3
"""Engraphis memory_provider for catcode.

Replaces the built-in markdown memory store. One script handles all six
memory actions the harness dispatches:

  inject         → proactive recall primed at session start
                   (GET /api/proactive_all + /api/stats)
  save / append  → store a durable fact / accumulate onto one
                   (POST /api/remember, dedupe=true)
  list           → memory-bank overview + top memories
                   (GET /api/stats + /api/proactive_all)
  forget         → retire a memory, bi-temporal close
                   (POST /api/forget)
  compact_append → a compaction extract (session summary) stored as an
                   episodic memory for later consolidation
                   (POST /api/remember, mtype=episodic, dedupe=false)

stdin (memory_provider contract):
  { "action": "save", "workspace": "/abs/path", "session_id": "...",
    "timestamp": 123, "args": { "name": ..., "content": ..., "scope": ... } }

stdout (one JSON object):
  inject:          { "ok": true, "injection": "..." }   ("" = no memories)
  save/append:     { "ok": true, "output": "...", "id": "..." }
  list:            { "ok": true, "output": "...", "entries": [...] }
  forget:          { "ok": true, "output": "..." }
  compact_append:  { "ok": true, "output": "..." }
  failure:         { "ok": false, "output": "reason" }

inject failures are soft (empty injection); write failures surface to the
model / slash-command caller. If the server is unreachable, writes return
ok:false with an actionable hint.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))

import engraphis as E  # noqa: E402


def _scope(args: dict, workspace_path: str):
    return E.resolve_scope(args.get("scope"), workspace_path)


# --------------------------------------------------------------------------- #
# actions
# --------------------------------------------------------------------------- #
def do_inject(args: dict, workspace_path: str) -> dict:
    query = args.get("query")
    try:
        stats = E.api("/api/stats", timeout=8.0) or {}
        n = int(stats.get("memories", 0) or 0)
        if n == 0:
            # empty memory bank — stay quiet, no injection
            return {"ok": True, "injection": ""}
        # query-aware recall if a query was supplied, else proactive across all
        if query:
            r = E.api("/api/recall", params={"q": query, "k": "5"}, timeout=8.0) or {}
            mems = r.get("memories", [])
        else:
            r = E.api("/api/proactive_all", params={"k": "5"}, timeout=8.0) or {}
            mems = r.get("memories", [])
        if not mems:
            return {"ok": True, "injection": ""}
        lines = [
            f"[Engraphis memory — {stats.get('memories', n)} memory(ies) across "
            f"{stats.get('workspaces', '?')} workspace(s). Use engraphis_recall to "
            f"search, engraphis_recall_grounded for a cited answer, the `memory` "
            f"tool to store durable facts.]",
            "What you should know right now:",
        ]
        for m in mems[:5]:
            lines.append(E.fmt_mem(m))
        return {"ok": True, "injection": "\n".join(lines)}
    except (E.ServerDown, E.ApiError):
        # soft: no injection, turn proceeds unaffected
        return {"ok": True, "injection": ""}


def _remember(args: dict, workspace_path: str, *, mtype: str, dedupe: bool,
              source: str) -> dict:
    ws, repo = _scope(args, workspace_path)
    name = args.get("name") or args.get("description") or ""
    content = args.get("content") or ""
    if not content:
        return {"ok": False, "output": "memory save: empty content"}
    try:
        imp = float(E.config()["default_importance"])
    except ValueError:
        imp = 0.0
    body = {
        "content": content,
        "workspace": ws,
        "repo": repo,
        "title": name,
        "mtype": args.get("type") or mtype,
        "importance": imp,
        "dedupe": dedupe,
        "source": source,
    }
    try:
        r = E.api("/api/remember", method="POST", body=body, timeout=30.0) or {}
    except E.ServerDown:
        return {"ok": False, "output": E.server_hint()}
    except E.ApiError as ex:
        return {"ok": False, "output": f"Engraphis remember failed: {ex}"}
    if not r.get("ok", True) and "ok" in r:
        return {"ok": False, "output": r.get("error", "remember failed")}
    loc = r.get("workspace", ws)
    if r.get("repo") or repo:
        loc += "/" + (r.get("repo") or repo)
    out = f"Remembered ({r.get('op', 'stored')}) → {r.get('id', '?')}  [workspace={loc}]"
    return {"ok": True, "output": out, "id": r.get("id", "")}


def do_save(args: dict, workspace_path: str) -> dict:
    return _remember(args, workspace_path, mtype="semantic", dedupe=True, source="agent")


def do_append(args: dict, workspace_path: str) -> dict:
    # append accumulates onto a same-named memory; Engraphis dedupe=true
    # reinforces/supersedes on conflict — the same happy path.
    return _remember(args, workspace_path, mtype="semantic", dedupe=True, source="agent")


def do_forget(args: dict, workspace_path: str) -> dict:
    mid = args.get("id")
    if not mid:
        return {"ok": False, "output": "forget: missing memory id"}
    ws, _ = _scope(args, workspace_path)
    try:
        r = E.api(
            "/api/forget",
            method="POST",
            body={"id": mid, "workspace": ws, "reason": args.get("reason") or "retired via memory tool"},
            timeout=20.0,
        ) or {}
    except E.ServerDown:
        return {"ok": False, "output": E.server_hint()}
    except E.ApiError as ex:
        return {"ok": False, "output": f"Engraphis forget failed: {ex}"}
    return {"ok": True, "output": f"Forgotten: {r.get('id', mid)} ({r.get('status', 'retired')})"}


def do_list(args: dict, workspace_path: str) -> dict:
    ws, _ = _scope(args, workspace_path)
    try:
        stats = E.api("/api/stats", params={"workspace": ws}, timeout=10.0) or {}
        top = E.api("/api/proactive_all", params={"k": "8"}, timeout=10.0) or {}
    except (E.ServerDown, E.ApiError):
        return {"ok": False, "output": E.server_hint()}
    mems = top.get("memories", []) or []
    by_type = stats.get("by_type", {}) or {}
    bt = " ".join(f"{k}:{v}" for k, v in by_type.items()) or "—"
    out = (
        f"{stats.get('memories', 0)} memories · {stats.get('workspaces', 0)} workspace(s) · "
        f"{stats.get('sessions', 0)} session(s)\nBy type: {bt}"
    )
    entries = []
    if mems:
        out += "\nTop memories:"
        for m in mems:
            out += "\n" + E.fmt_mem(m)
            entries.append({"id": m.get("id"), "title": m.get("title"), "type": m.get("memory_type")})
    return {"ok": True, "output": out, "entries": entries}


def do_compact_append(args: dict, workspace_path: str) -> dict:
    # A compaction extract is a session summary — store as an episodic memory
    # (dedupe=false so each session is distinct) for later consolidation.
    content = args.get("content") or ""
    if not content:
        return {"ok": False, "output": "compact_append: empty content"}
    ws, repo = _scope(args, workspace_path)
    name = args.get("name") or "session-compaction"
    body = {
        "content": content,
        "workspace": ws,
        "repo": repo,
        "title": name,
        "mtype": "episodic",
        "importance": 0.0,
        "dedupe": False,
        "source": "compaction",
    }
    try:
        r = E.api("/api/remember", method="POST", body=body, timeout=30.0) or {}
    except E.ServerDown:
        return {"ok": False, "output": E.server_hint()}
    except E.ApiError as ex:
        return {"ok": False, "output": f"Engraphis compact_append failed: {ex}"}
    return {"ok": True, "output": f"Compaction stored → {r.get('id', '?')}  [workspace={ws}]"}


_DISPATCH = {
    "inject": do_inject,
    "save": do_save,
    "append": do_append,
    "forget": do_forget,
    "list": do_list,
    "compact_append": do_compact_append,
}


def main() -> None:
    ctx = E.read_ctx()
    action = ctx.get("action", "")
    args = ctx.get("args") or {}
    workspace_path = ctx.get("workspace")
    handler = _DISPATCH.get(action)
    if handler is None:
        E.emit({"ok": False, "output": f"engraphis memory_provider: unknown action '{action}'"})
        return
    try:
        E.emit(handler(args, workspace_path))
    except Exception as ex:  # never crash the core
        E.emit({"ok": False, "output": f"engraphis memory_provider error ({action}): {ex}"})


if __name__ == "__main__":
    main()
