#!/usr/bin/env python3
"""engraphis_timeline — bi-temporal history of a topic.

What was believed and when, oldest first. Use to trace how a fact evolved.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, _ = E.resolve_tool_scope(args, ctx.get("workspace"))
    topic = args.get("topic") or ""
    try:
        r = E.api(
            "/api/timeline",
            params={"q": topic, "workspace": ws, "limit": "40"},
            timeout=20.0,
        ) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis timeline failed: {ex}"})
        return
    hist = r.get("history", []) or []
    if not hist:
        E.emit({"ok": True, "output": f'No history for "{topic}".'})
        return
    lines = []
    for m in hist:
        current = not (m.get("valid_to") or m.get("expired_at"))
        lines.append(E.fmt_mem(m) + (" [current]" if current else " [past]"))
    E.emit({"ok": True, "output": "\n".join(lines)})


if __name__ == "__main__":
    main()
