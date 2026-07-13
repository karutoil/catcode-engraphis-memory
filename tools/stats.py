#!/usr/bin/env python3
"""engraphis_stats — overview of the memory bank.

Total memories, breakdown by type, workspaces, sessions.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    # stats uses the Engraphis native workspace param directly (omit = all)
    ws = args.get("workspace") or E.config()["default_ws"]
    scope = args.get("scope")
    if scope == "global":
        ws = E.config()["global_ws"]
    params = {"workspace": ws} if args.get("workspace") or scope else {}
    try:
        r = E.api("/api/stats", params=params, timeout=10.0) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis stats failed: {ex}"})
        return
    by_type = r.get("by_type", {}) or {}
    bt = " ".join(f"{k}:{v}" for k, v in by_type.items()) or "—"
    out = (
        f"{r.get('memories', 0)} memories · {r.get('workspaces', 0)} workspace(s) · "
        f"{r.get('sessions', 0)} session(s)\nBy type: {bt}"
    )
    E.emit({"ok": True, "output": out})


if __name__ == "__main__":
    main()
