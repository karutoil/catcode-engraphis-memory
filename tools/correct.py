#!/usr/bin/env python3
"""engraphis_correct — supersede a memory with new content.

The old version is closed (kept in history, never deleted) and the new
content becomes current truth. Prefer this over forget+remember when you
have replacement content — it preserves the supersession chain
(visible via engraphis_why / engraphis_timeline).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, _ = E.resolve_tool_scope(args, ctx.get("workspace"))
    mid = args.get("id") or ""
    content = args.get("content") or ""
    if not mid or not content:
        E.emit({"ok": False, "output": "engraphis_correct: missing id or content"})
        return
    try:
        r = E.api(
            "/api/correct",
            method="POST",
            body={
                "id": mid,
                "workspace": ws,
                "content": content,
                "reason": args.get("reason") or "corrected",
            },
            timeout=20.0,
        ) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis correct failed: {ex}"})
        return
    out = f"Corrected: {r.get('id', mid)} → {r.get('superseded_by', '(new version)')}"
    E.emit({"ok": True, "output": out})


if __name__ == "__main__":
    main()
