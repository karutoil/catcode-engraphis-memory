# engraphis-memory

A [Catalyst Code](https://github.com/catalystctl/catalyst-code) plugin that
replaces the built-in markdown memory store with
[**Engraphis**](https://github.com/earendil-works/engraphis) — persistent,
scoped, bi-temporal, explainable memory for your coding agent.

This is a port of the pi/OMP `engraphis` TypeScript extension to the catcode
plugin model. The agent's long-term memory now lives in a self-hosted Engraphis
server instead of flat markdown files, gaining hybrid semantic search, cited
grounded answers, supersession history, decay/consolidation, and cross-session
recall.

---

## What it does

When loaded, this plugin **replaces the default memory backend**:

| catcode surface | routes to Engraphis via… |
|---|---|
| Standing-prompt injection (session priming) | `memory_provider` `inject` → `GET /api/proactive_all` |
| `memory` tool `save` / `append` | `POST /api/remember` (dedupe) |
| `memory` tool `forget` | `POST /api/forget` (bi-temporal close) |
| `memory` tool `list` | `GET /api/stats` + `/api/proactive_all` |
| `/remember`, `/memory`, `/forget` slash commands | same provider actions |
| Compaction extract (`compact_append`) | `POST /api/remember` (episodic, for later consolidation) |
| Auto-reflect loop writes | the `memory` tool → provider |

The built-in `memory` tool keeps its standard schema, so auto-reflect and slash
commands work unchanged — they just persist to Engraphis now.

On top of that, **ten extra tools** expose Engraphis's query & curation surface
that has no catcode equivalent:

| Tool | Engraphis endpoint | Kind | Use when |
|---|---|---|---|
| `engraphis_recall` | `GET /api/recall` | readonly | search memory for a list of matches |
| `engraphis_recall_grounded` | `POST /api/grounded` | readonly | need a cited *answer*, or an explicit abstain |
| `engraphis_why` | `GET /api/why` | readonly | explain why something is the way it is (incl. superseded facts) |
| `engraphis_timeline` | `GET /api/timeline` | readonly | trace how a fact evolved over time |
| `engraphis_stats` | `GET /api/stats` | readonly | memory-bank overview (counts by type/workspace) |
| `engraphis_pin` | `POST /api/pin` | destructive | exempt a memory from decay/pruning |
| `engraphis_correct` | `POST /api/correct` | destructive | supersede a wrong memory with replacement content |
| `engraphis_consolidate` | `POST /api/consolidate` | destructive | sleep-time distillation sweep (episodic→semantic) |
| `engraphis_link` | `POST /api/link` | destructive | connect two related memories |
| `engraphis_record_event` | `POST /api/record_event` | destructive | lightweight episodic log entry |

### PI → catcode mapping

The original pi plugin exposed 12 tools. In catcode, `engraphis_remember` and
`engraphis_forget` are absorbed by the built-in `memory` tool (routed through
the `memory_provider`), so auto-reflect and slash commands keep working. The
remaining ten become first-class plugin tools:

```
pi tool                      → catcode
─────────────────────────────────────────────────────────────
session_start priming        → memory_provider inject
engraphis_remember           → memory tool (save/append)
engraphis_forget             → memory tool (forget)
/list, /memory               → memory_provider list
compaction                   → memory_provider compact_append
engraphis_recall             → tool (readonly)
engraphis_recall_grounded    → tool (readonly)
engraphis_why                → tool (readonly)
engraphis_timeline           → tool (readonly)
engraphis_stats              → tool (readonly)
engraphis_pin                → tool (destructive)
engraphis_correct            → tool (destructive)
engraphis_consolidate        → tool (destructive)
engraphis_link               → tool (destructive)
engraphis_record_event       → tool (destructive)
```

### Scope mapping

catcode's two-level memory scope maps onto Engraphis's (workspace, repo):

| catcode `scope` | Engraphis `workspace` | Engraphis `repo` |
|---|---|---|
| `workspace` (per-codebase, default) | `default` (or `ENGRAPHIS_WORKSPACE`) | basename of the workspace path |
| `global` (cross-codebase) | `global` (or `ENGRAPHIS_GLOBAL_WS`) | — |

Repo auto-derivation ignores junk basenames (`tmp`, `home`, `workspace`, …);
the ten tools also accept explicit `workspace` / `repo` params.

---

## Requirements

- **A running Engraphis server** (loopback, single-user). See the
  [Engraphis repo](https://github.com/earendil-works/engraphis); maintain it with
  `engraphis-update`. Default endpoint `http://127.0.0.1:8700`.
- **Python 3.9+** on the machine running catcode (stdlib only — `urllib`,
  `json`; no pip packages).
- catcode with plugin support (the `memory_provider` + `tools` manifest fields).

If the server is unreachable, the plugin **degrades gracefully**: `inject`
returns an empty injection (the turn proceeds unaffected), and all other
actions return `ok: false` with an actionable hint instead of crashing the turn.

---

## Configuration

All optional — a loopback single-user Engraphis needs none:

| Env var | Default | Purpose |
|---|---|---|
| `ENGRAPHIS_URL` | `http://127.0.0.1:8700` | server base URL |
| `ENGRAPHIS_WORKSPACE` | `default` | top-level scope for `workspace`-scoped memories |
| `ENGRAPHIS_GLOBAL_WS` | `global` | scope used for catcode `global` memories |
| `ENGRAPHIS_API_TOKEN` | _(empty)_ | bearer token, only if the server sets one |
| `ENGRAPHIS_DEFAULT_IMPORTANCE` | `0.0` | salience 0–1 for auto-saved facts (decay resistance) |

---

## Install

### From a local checkout

```bash
# global (every workspace) — recommended for a memory backend
/plugin-install /path/to/catcode-engraphis-memory

# or repo-local only
/plugin-install /path/to/catcode-engraphis-memory workspace
```

### From GitHub (once you publish a Release)

```bash
/plugin-install https://github.com/<owner>/catcode-engraphis-memory
# pinned:
/plugin-install <owner>/catcode-engraphis-memory@v0.1.0
```

> Only **one** `memory_provider` should be active at a time. Disable the
> built-in markdown store by loading this plugin (the core skips the markdown
> store automatically when a provider is loaded). Restart catcode (or use the
> `plugin` tool) after installing.

### Verify

Once the Engraphis server is up, restart catcode and check the session-start
priming, then:

```
/memory            → list (via provider → /api/stats)
engraphis_stats    → memory-bank overview
engraphis_recall   → "build tooling"
```

To migrate memories from an Engraphis DB used by another harness, see the
`migrate-engraphis-db` skill (`ENGRAPHIS_DB_PATH` / `~/.config/catalyst-code/engraphis/`).

---

## Layout

```
catcode-engraphis-memory/
├── plugin.json           # manifest: memory_provider + 10 tools + system_prompt
├── lib/
│   └── engraphis.py      # shared HTTP client (urllib, no deps), scope + format helpers
├── memory/
│   └── provider.py       # memory_provider: inject/save/append/list/forget/compact_append
├── tools/
│   ├── recall.py
│   ├── recall_grounded.py
│   ├── why.py
│   ├── timeline.py
│   ├── stats.py
│   ├── pin.py
│   ├── correct.py
│   ├── consolidate.py
│   ├── link.py
│   └── record_event.py
├── scripts/
│   └── dry-run.sh        # smoke test: pipes mock JSON to every handler
├── README.md
└── LICENSE
```

Each tool/provider script is a thin handler that imports `lib/engraphis.py`
(via a `sys.path` shim relative to its own location), reads one JSON object on
stdin, calls the Engraphis HTTP API, and writes one JSON object on stdout.

---

## Smoke test

```bash
bash scripts/dry-run.sh
```

Pipes mock context JSON to every handler. With no server running, it verifies
graceful degradation: `inject` → empty injection, everything else → `ok:false`
with the server hint, never a crash.

## License

MIT
