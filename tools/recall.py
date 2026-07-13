#!/usr/bin/env python3
"""engraphis_recall — hybrid semantic + lexical + retention search.

Returns a LIST of matching memories with scores. Use to find relevant past
facts before answering or acting.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, _ = E.resolve_tool_scope(args, ctx.get("workspace"))
    query = args.get("query") or ""
    k = args.get("k") or 5
    try:
        r = E.api("/api/recall", params={"q": query, "workspace": ws, "k": str(k)}, timeout=20.0) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis recall failed: {ex}"})
        return
    mems = r.get("memories", []) or []
    if not mems:
        E.emit({"ok": True, "output": f'No memories matched "{query}".'})
        return
    out = "\n".join(E.fmt_mem(m) for m in mems)
    noun = "memory" if len(mems) == 1 else "memories"
    E.emit({"ok": True, "output": f"{len(mems)} {noun} ({r.get('mode', 'semantic')}):\n{out}"})


if __name__ == "__main__":
    main()
