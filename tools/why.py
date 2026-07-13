#!/usr/bin/env python3
"""engraphis_why — the current answer AND what it superseded.

Shows both the current truth and superseded facts (what changed and when).
Use to explain why something is the way it is.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, _ = E.resolve_tool_scope(args, ctx.get("workspace"))
    question = args.get("question") or ""
    try:
        r = E.api("/api/why", params={"q": question, "workspace": ws}, timeout=20.0) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis why failed: {ex}"})
        return
    cur = r.get("answer", []) or []
    cur_txt = "\n".join(E.fmt_mem(m) for m in cur) if cur else "(no current answer)"
    old = r.get("supersedes", []) or []
    out = f"Current:\n{cur_txt}"
    if old:
        out += "\n\nSuperseded (no longer true):\n" + "\n".join(E.fmt_mem(m) for m in old)
    E.emit({"ok": True, "output": out})


if __name__ == "__main__":
    main()
