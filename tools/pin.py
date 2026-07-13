#!/usr/bin/env python3
"""engraphis_pin — pin a memory so it is exempt from decay and pruning.

Use for important conventions that must persist.
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
    if not mid:
        E.emit({"ok": False, "output": "engraphis_pin: missing memory id"})
        return
    try:
        r = E.api(
            "/api/pin",
            method="POST",
            body={"id": mid, "workspace": ws, "pinned": True},
            timeout=20.0,
        ) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis pin failed: {ex}"})
        return
    E.emit({"ok": True, "output": f"Pinned: {r.get('id', mid)}"})


if __name__ == "__main__":
    main()
