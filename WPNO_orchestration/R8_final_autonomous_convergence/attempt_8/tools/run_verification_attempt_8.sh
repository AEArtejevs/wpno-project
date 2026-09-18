#!/usr/bin/env bash
# The attempt-8 verification RUNNER.
#
# This script is the verifier's launcher. It is not the verification result,
# and the verification result is not a verifier -- that conflation was one of
# attempt 4's defects.
#
# ONE fresh Codex process. No `resume`, no `fork`, no reuse of any earlier
# attempt's thread. CODEX_HOME is not read, not set and not modified here. No
# login, no logout.
#
# Two writable roots and no more: the attempt workspace (-C) and the
# disposable sibling clone (--add-dir). ORIGINAL R8 is in neither, so
# `--sandbox workspace-write` makes it read-only at kernel level rather than
# by request. That barrier is proved to refuse a write BEFORE it is relied on;
# see logs/SANDBOX_PROBE_RECORD.json.
#
# Completion is determined by waiting on the exact PID, never by watching for
# an output file to appear and never by searching command lines.

set -u -o pipefail

A8_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
R8_ROOT="/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
PROMPT_FILE="$A8_ROOT/tools/VERIFY_PROMPT_ATTEMPT_8.md"
CLONE="$(cat "$A8_ROOT/preflight/CLONE_PATH.txt")"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$A8_ROOT/temporary/pycache"
export TMPDIR="$A8_ROOT/temporary"
export TEMP="$A8_ROOT/temporary"
export TMP="$A8_ROOT/temporary"
export PYTEST_ADDOPTS="-p no:cacheprovider"
export COVERAGE_FILE="$A8_ROOT/temporary/.coverage"

mkdir -p "$A8_ROOT/codex_output" "$A8_ROOT/logs" "$A8_ROOT/temporary/pycache"

fail() { echo "RUNNER_FAIL: $1" >&2; exit 2; }

[ -d "$CLONE" ] || fail "the disposable sibling clone is absent: $CLONE"
[ "$(dirname "$CLONE")" = "/home/ubuntu/project/WPNO" ] \
  || fail "the clone is not a direct sibling of R8: $CLONE"
[ -f "$A8_ROOT/preflight/PREFLIGHT.json" ] || fail "no preflight record"
grep -q '"PREFLIGHT_PASS": true' "$A8_ROOT/preflight/PREFLIGHT.json" \
  || fail "preflight did not pass"
[ -f "$A8_ROOT/original_inventory/INVENTORY_PRE.json" ] \
  || fail "the pre-verification inventory is absent"
[ -f "$A8_ROOT/TOOL_INVENTORY.json" ] || fail "the tool inventory is absent"
grep -q '"UNIDENTIFIED_TOOLS": 0' "$A8_ROOT/TOOL_INVENTORY.json" \
  || fail "the tool inventory reports unidentified tools"
[ -f "$A8_ROOT/logs/SANDBOX_PROBE_RECORD.json" ] \
  || fail "the write barrier has not been proved to refuse a write"
grep -q '"BARRIER_PROVED": true' "$A8_ROOT/logs/SANDBOX_PROBE_RECORD.json" \
  || fail "the write barrier was not proved effective"

{
  echo "runner_started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "codex_version=$(codex --version)"
  echo "workspace_root=$A8_ROOT"
  echo "writable_clone=$CLONE"
  echo "r8_root_readonly=$R8_ROOT"
  echo "prompt_sha256=$(/usr/bin/sha256sum "$PROMPT_FILE" | cut -d' ' -f1)"
  echo "runner_sha256=$(/usr/bin/sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)"
} > "$A8_ROOT/logs/runner_context.txt"

# The prompt goes in on stdin so no part of it is subject to shell expansion.
# --skip-git-repo-check because the workspace is not a git repository and must
# not become one.
codex exec \
  --sandbox workspace-write \
  -C "$A8_ROOT" \
  --add-dir "$CLONE" \
  --skip-git-repo-check \
  - < "$PROMPT_FILE" \
  > "$A8_ROOT/logs/codex_attempt_8.stdout.txt" \
  2> "$A8_ROOT/logs/codex_attempt_8.stderr.txt" &

CODEX_PID=$!
echo "codex_pid=$CODEX_PID" >> "$A8_ROOT/logs/runner_context.txt"
echo "$CODEX_PID" > "$A8_ROOT/logs/codex.pid"

# Wait on the exact process handle. Not on a file appearing, not on a name.
wait "$CODEX_PID"
status=$?

echo "codex_exit_status=$status" >> "$A8_ROOT/logs/runner_context.txt"
echo "runner_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> "$A8_ROOT/logs/runner_context.txt"
exit $status
