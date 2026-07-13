#!/usr/bin/env python3
"""engraphis_link — explicitly connect two related memories.

Use when a plain recall wouldn't surface two stored facts as connected
(e.g. a bug report and the memory describing the fix).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, _ = E.resolve_tool_scope(args, ctx.get("workspace"))
    a = args.get("a") or ""
    b = args.get("b") or ""
    if not a or not b:
        E.emit({"ok": False, "output": "engraphis_link: need both memory ids (a, b)"})
        return
    relation = args.get("relation") or "related"
    try:
        r = E.api(
            "/api/link",
            method="POST",
            body={"a": a, "b": b, "workspace": ws, "relation": relation},
            timeout=20.0,
        ) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis link failed: {ex}"})
        return
    if not r.get("ok", True) and "ok" in r:
        E.emit({"ok": False, "output": r.get("error", "link failed")})
        return
    E.emit({"ok": True, "output": f"Linked: {r.get('a', a)} —[{r.get('relation', relation)}]→ {r.get('b', b)}"})


if __name__ == "__main__":
    main()
