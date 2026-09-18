#!/usr/bin/env bash
# The final verification RUNNER for the lineage-repaired package.
#
# The launcher. It is not the verification result, and the verification result
# is not a verifier.
#
# ONE fresh Codex process. No `resume`, no `fork`. CODEX_HOME is not read, not
# set and not modified. No login, no logout. Two writable roots: this workspace
# (-C) and the disposable sibling clone (--add-dir). ORIGINAL R8 is in neither,
# so `--sandbox workspace-write` makes it read-only at kernel level rather than
# by request, and the barrier is proved to refuse a write before it is relied
# on.
#
# Completion is determined by waiting on the exact PID, never by watching for
# an output file to appear and never by searching command lines.
#
# `-e` as well as `-u -o pipefail`, as the static-safety review requires. The
# one place it would change behaviour is the `wait`, whose purpose is to
# CAPTURE a non-zero status rather than die on it; that call states
# `|| status=$?`, so the runner still records the context and the exit code.
set -e -u -o pipefail

OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
R8_ROOT="/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
PROMPT_FILE="$OUT/tools/VERIFY_PROMPT_LINEAGE_FINAL.md"
CLONE="$(cat "$OUT/preflight/CLONE_PATH.txt")"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$OUT/temporary/pycache"
export TMPDIR="$OUT/temporary"
export TEMP="$OUT/temporary"
export TMP="$OUT/temporary"
export PYTEST_ADDOPTS="-p no:cacheprovider"
export COVERAGE_FILE="$OUT/temporary/.coverage"

mkdir -p "$OUT/codex_output" "$OUT/logs" "$OUT/temporary/pycache"

fail() { echo "RUNNER_FAIL: $1" >&2; exit 2; }

[ -d "$CLONE" ] || fail "the disposable sibling clone is absent: $CLONE"
[ "$(dirname "$CLONE")" = "/home/ubuntu/project/WPNO" ] \
  || fail "the clone is not a direct sibling of R8: $CLONE"
grep -q '"PREFLIGHT_PASS": true' "$OUT/preflight/PREFLIGHT.json" \
  || fail "clone preflight did not pass"
grep -q '"UNIDENTIFIED_TOOLS": 0' "$OUT/TOOL_INVENTORY.json" \
  || fail "the tool inventory reports unidentified tools"
grep -q '"UNRESOLVED_KEY_LOOKUPS": 0' "$OUT/VERIFIER_SCHEMA_MAP.json" \
  || fail "the schema map has unresolved key lookups"
grep -q '"BARRIER_PROVED": true' "$OUT/logs/SANDBOX_PROBE_RECORD.json" \
  || fail "the write barrier was not proved effective"
[ -f "$OUT/inventory/INVENTORY_PRE.json" ] \
  || fail "the pre-verification inventory is absent"

{
  echo "runner_started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "codex_version=$(codex --version)"
  echo "workspace_root=$OUT"
  echo "writable_clone=$CLONE"
  echo "r8_root_readonly=$R8_ROOT"
  echo "prompt_sha256=$(/usr/bin/sha256sum "$PROMPT_FILE" | cut -d' ' -f1)"
  echo "runner_sha256=$(/usr/bin/sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)"
} > "$OUT/logs/runner_context.txt"

codex exec \
  --sandbox workspace-write \
  -C "$OUT" \
  --add-dir "$CLONE" \
  --skip-git-repo-check \
  - < "$PROMPT_FILE" \
  > "$OUT/logs/codex_lineage.stdout.txt" \
  2> "$OUT/logs/codex_lineage.stderr.txt" &

CODEX_PID=$!
echo "codex_pid=$CODEX_PID" >> "$OUT/logs/runner_context.txt"
echo "$CODEX_PID" > "$OUT/logs/codex.pid"

status=0
wait "$CODEX_PID" || status=$?

echo "codex_exit_status=$status" >> "$OUT/logs/runner_context.txt"
echo "runner_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> "$OUT/logs/runner_context.txt"
exit "$status"
