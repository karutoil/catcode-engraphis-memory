#!/usr/bin/env python3
"""engraphis_recall_grounded — a cited ANSWER from memory, or explicit abstain.

Offline/deterministic (no LLM synthesis). Use when you need an answer, not a
list. Returns {grounded, abstained, answer, support, citations, reason}.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import engraphis as E  # noqa: E402


def main() -> None:
    ctx = E.read_ctx()
    args = ctx.get("args") or {}
    ws, repo = E.resolve_tool_scope(args, ctx.get("workspace"))
    query = args.get("query") or ""
    k = args.get("k") or 8
    try:
        r = E.api(
            "/api/grounded",
            method="POST",
            body={"query": query, "workspace": ws, "repo": repo, "k": k},
            timeout=25.0,
        ) or {}
    except E.ServerDown:
        E.emit({"ok": False, "output": E.server_hint()})
        return
    except E.ApiError as ex:
        E.emit({"ok": False, "output": f"Engraphis grounded recall failed: {ex}"})
        return
    if not r.get("ok", True):
        E.emit({"ok": False, "output": r.get("error", "grounded recall failed")})
        return
    if r.get("abstained"):
        support = r.get("support", 0)
        try:
            support = f"{float(support):.2f}"
        except (TypeError, ValueError):
            pass
        E.emit({
            "ok": True,
            "output": (
                f'Insufficient evidence to answer "{query}".\n'
                f'Reason: {r.get("reason", "support below threshold")} (support={support})'
            ),
        })
        return
    cites = r.get("citations", []) or []
    cite_txt = "\n".join(
        f"  [{i + 1}] {c.get('title') or c.get('id')}: {str(c.get('content') or '')[:200]}"
        for i, c in enumerate(cites)
    ) or "(none)"
    E.emit({"ok": True, "output": f"{r.get('answer', '')}\n\nCitations:\n{cite_txt}"})


if __name__ == "__main__":
    main()
