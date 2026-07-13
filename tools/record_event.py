#!/usr/bin/env python3
"""engraphis_record_event — append a lightweight episodic log entry.

Lower ceremony than the `memory` tool for raw events you may later want
consolidated into a durable fact (e.g. 'tried X, it deadlocked'). Use the
`memory` tool for crisp durable facts; use this for event logs that
accumulate.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, repo = E.resolve_tool_scope(args, ctx.get("workspace"))
    kind = args.get("kind") or "observation"
    content = args.get("content") or ""
    if not content:
        E.emit({"ok": False, "output": "engraphis_record_event: missing content"})
        return
    try:
        r = E.api(
            "/api/record_event",
            method="POST",
            body={"kind": kind, "content": content, "workspace": ws, "repo": repo},
            timeout=20.0,
        ) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis record_event failed: {ex}"})
        return
    if not r.get("ok", True) and "ok" in r:
        E.emit({"ok": False, "output": r.get("error", "record_event failed")})
        return
    E.emit({"ok": True, "output": f"Logged event ({r.get('kind', kind)}): {r.get('id', '?')}"})


if __name__ == "__main__":
    main()
