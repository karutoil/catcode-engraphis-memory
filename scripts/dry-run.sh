#!/usr/bin/env bash
# Dry-run every engraphis-memory handler with mock stdin.
# The server is down, so this verifies GRACEFUL DEGRADATION only:
#   - inject → empty injection (soft)
#   - writes → ok:false with server hint (surfaces)
#   - reads  → ok:false with server hint
#   - never crashes, always emits one JSON object
set -u
cd "$(dirname "$0")/.."
WS="$(pwd)"

run() { # name stdin_file cmd...
  local name="$1" stdin="$2"; shift 2
  printf '%s\n' "--- $name ---"
  "$@" < "$stdin" 2>/tmp/eng_err
  local rc=$?
  if [ $rc -ne 0 ]; then printf 'EXIT %d\n' "$rc"; fi
  if [ -s /tmp/eng_err ]; then printf 'STDERR: %s\n' "$(cat /tmp/eng_err)"; fi
}

# memory_provider actions
printf '{"action":"inject","workspace":"%s","session_id":"s","timestamp":1,"args":{}}' "$WS" > /tmp/in.json
printf '{"action":"save","workspace":"%s","session_id":"s","timestamp":1,"args":{"name":"test","content":"We use pnpm not npm.","scope":"workspace"}}' "$WS" > /tmp/save.json
printf '{"action":"append","workspace":"%s","session_id":"s","timestamp":1,"args":{"name":"conv","content":"appended fact","scope":"global"}}' "$WS" > /tmp/append.json
printf '{"action":"list","workspace":"%s","session_id":"s","timestamp":1,"args":{}}' "$WS" > /tmp/list.json
printf '{"action":"forget","workspace":"%s","session_id":"s","timestamp":1,"args":{"id":"mem-123","scope":"workspace"}}' "$WS" > /tmp/forget.json
printf '{"action":"compact_append","workspace":"%s","session_id":"s","timestamp":1,"args":{"name":"sess-compaction","content":"session summary here","cap_bytes":4096}}' "$WS" > /tmp/compact.json
printf '{"action":"bogus","workspace":"%s","session_id":"s","timestamp":1,"args":{}}' "$WS" > /tmp/bogus.json

run "inject (soft→empty)"       /tmp/in.json      ./memory/provider.py
run "save (→ok:false hint)"     /tmp/save.json    ./memory/provider.py
run "append (global scope)"     /tmp/append.json  ./memory/provider.py
run "list"                      /tmp/list.json    ./memory/provider.py
run "forget"                    /tmp/forget.json  ./memory/provider.py
run "compact_append"            /tmp/compact.json ./memory/provider.py
run "unknown action"            /tmp/bogus.json   ./memory/provider.py

# tool handlers — contract: {args, workspace, session_id, timestamp}
printf '{"args":{"query":"pnpm convention"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/recall.json
printf '{"args":{"query":"what build tool?"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/grounded.json
printf '{"args":{"question":"why pnpm?"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/why.json
printf '{"args":{"topic":"build tooling"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/tl.json
printf '{"args":{},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/stats.json
printf '{"args":{"id":"mem-1"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/pin.json
printf '{"args":{"id":"mem-1","content":"corrected content"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/corr.json
printf '{"args":{"dry_run":true},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/cons.json
printf '{"args":{"a":"m1","b":"m2","relation":"fixes"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/link.json
printf '{"args":{"kind":"attempt","content":"tried X, deadlocked"},"workspace":"%s","session_id":"s","timestamp":1}' "$WS" > /tmp/evt.json

run "recall (readonly)"         /tmp/recall.json  ./tools/recall.py
run "recall_grounded (readonly)" /tmp/grounded.json ./tools/recall_grounded.py
run "why (readonly)"             /tmp/why.json    ./tools/why.py
run "timeline (readonly)"        /tmp/tl.json     ./tools/timeline.py
run "stats (readonly)"           /tmp/stats.json  ./tools/stats.py
run "pin (destructive)"          /tmp/pin.json     ./tools/pin.py
run "correct (destructive)"      /tmp/corr.json   ./tools/correct.py
run "consolidate (destructive)"  /tmp/cons.json    ./tools/consolidate.py
run "link (destructive)"         /tmp/link.json    ./tools/link.py
run "record_event (destructive)" /tmp/evt.json     ./tools/record_event.py

echo
echo "=== empty-content validation paths ==="
printf '{"action":"save","workspace":"%s","args":{"name":"x","content":""}}' "$WS" > /tmp/empty.json
run "save empty content"         /tmp/empty.json   ./memory/provider.py
printf '{"args":{"query":""},"workspace":"%s"}' "$WS" > /tmp/eq.json
run "recall (missing query→no match)" /tmp/eq.json ./tools/recall.py
