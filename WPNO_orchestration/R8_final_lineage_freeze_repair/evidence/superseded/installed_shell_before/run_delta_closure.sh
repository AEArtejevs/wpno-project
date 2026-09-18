#!/usr/bin/env bash
# The delta-closure verification RUNNER.
#
# The launcher. It is not the verification result, and the verification result
# is not a verifier.
#
# ONE fresh Codex process. No `resume`, no `fork`. CODEX_HOME is not read, not
# set and not modified. No login, no logout.
#
# Two writable roots: the closure workspace (-C) and the disposable sibling
# clone (--add-dir), the latter only so that importing R8's `automation` cannot
# leave a __pycache__ inside the package. ORIGINAL R8 is in neither, so
# `--sandbox workspace-write` makes it read-only at kernel level rather than by
# request, and that barrier is proved to refuse a write before it is relied on.
#
# Completion is determined by waiting on the exact PID, never by watching for
# an output file to appear and never by searching command lines.

set -u -o pipefail

FR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
R8_ROOT="/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
PROMPT_FILE="$FR/tools/DELTA_VERIFY_PROMPT.md"
CLONE="$(cat "$FR/preflight/CLONE_PATH.txt")"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$FR/temporary/pycache"
export TMPDIR="$FR/temporary"
export TEMP="$FR/temporary"
export TMP="$FR/temporary"
export PYTEST_ADDOPTS="-p no:cacheprovider"
export COVERAGE_FILE="$FR/temporary/.coverage"

mkdir -p "$FR/codex_output" "$FR/logs" "$FR/temporary/pycache"

fail() { echo "RUNNER_FAIL: $1" >&2; exit 2; }

[ -d "$CLONE" ] || fail "the disposable sibling clone is absent: $CLONE"
[ "$(dirname "$CLONE")" = "/home/ubuntu/project/WPNO" ] \
  || fail "the clone is not a direct sibling of R8: $CLONE"
grep -q '"PREFLIGHT_PASS": true' "$FR/preflight/PREFLIGHT.json" \
  || fail "clone preflight did not pass"
grep -q '"FIXED_TARGET_UNCHANGED": true' "$FR/preflight/FIXED_TARGET.json" \
  || fail "the fixed R8 target has moved"
grep -q '"DELTA_VERIFIER_SELF_TEST": "PASS"' \
  "$FR/selftest/DELTA_VERIFIER_SELFTEST.json" \
  || fail "the delta verifier self-test has not passed; no attempt is spent"
grep -q '"UNIDENTIFIED_TOOLS": 0' "$FR/TOOL_INVENTORY.json" \
  || fail "the tool inventory reports unidentified tools"
grep -q '"BARRIER_PROVED": true' "$FR/logs/SANDBOX_PROBE_RECORD.json" \
  || fail "the write barrier was not proved effective"
[ -f "$FR/inventory/INVENTORY_PRE.json" ] \
  || fail "the pre-verification inventory is absent"

{
  echo "runner_started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "codex_version=$(codex --version)"
  echo "workspace_root=$FR"
  echo "writable_clone=$CLONE"
  echo "r8_root_readonly=$R8_ROOT"
  echo "prompt_sha256=$(/usr/bin/sha256sum "$PROMPT_FILE" | cut -d' ' -f1)"
  echo "runner_sha256=$(/usr/bin/sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)"
} > "$FR/logs/runner_context.txt"

codex exec \
  --sandbox workspace-write \
  -C "$FR" \
  --add-dir "$CLONE" \
  --skip-git-repo-check \
  - < "$PROMPT_FILE" \
  > "$FR/logs/codex_delta.stdout.txt" \
  2> "$FR/logs/codex_delta.stderr.txt" &

CODEX_PID=$!
echo "codex_pid=$CODEX_PID" >> "$FR/logs/runner_context.txt"
echo "$CODEX_PID" > "$FR/logs/codex.pid"

wait "$CODEX_PID"
status=$?

echo "codex_exit_status=$status" >> "$FR/logs/runner_context.txt"
echo "runner_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> "$FR/logs/runner_context.txt"
exit $status
