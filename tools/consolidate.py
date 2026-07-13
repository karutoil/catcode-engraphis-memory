#!/usr/bin/env python3
"""engraphis_consolidate — sleep-time consolidation sweep.

Recurring episodic memories on the same subject are distilled into one
durable semantic digest, and fully-decayed transient memories are archived.
Use periodically to keep the memory bank lean. dry_run=true previews only.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402

import json


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, _ = E.resolve_tool_scope(args, ctx.get("workspace"))
    dry = bool(args.get("dry_run"))
    try:
        r = E.api(
            "/api/consolidate",
            method="POST",
            body={"workspace": ws, "dry_run": dry},
            timeout=60.0,
        )
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis consolidate failed: {ex}"})
        return
    label = "Dry run (nothing changed)" if dry else "Consolidation complete"
    E.emit({"ok": True, "output": f"{label}:\n{json.dumps(r, indent=2, ensure_ascii=False)}"})


if __name__ == "__main__":
    main()
