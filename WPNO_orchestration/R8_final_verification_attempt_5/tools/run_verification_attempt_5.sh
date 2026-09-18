#!/usr/bin/env bash
# The attempt-5 verification RUNNER.
#
# This script is the verifier's launcher. It is not the verification result,
# and the verification result is not a verifier -- that conflation is one of
# the attempt-4 defects this attempt records.
#
# It launches ONE fresh Codex process. No /resume, no fork, no reuse of any
# earlier attempt's thread. CODEX_HOME is not modified and not set here.
#
# Write isolation is enforced by the sandbox, not requested politely: the
# codex workspace root is ATTEMPT5_ROOT, R8 lies outside it, and
# `--sandbox workspace-write` makes everything outside the workspace root
# read-only at kernel level. That barrier was proved to refuse a write before
# it was relied on; see logs/SANDBOX_PROBE_RECORD.json.

set -u -o pipefail

A5_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
R8_ROOT="/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
PROMPT_FILE="$A5_ROOT/tools/VERIFY_PROMPT_ATTEMPT_5.md"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$A5_ROOT/temporary/pycache"
export TMPDIR="$A5_ROOT/temporary"
export TEMP="$A5_ROOT/temporary"
export TMP="$A5_ROOT/temporary"
export PYTEST_ADDOPTS="-p no:cacheprovider"
export COVERAGE_FILE="$A5_ROOT/temporary/.coverage"

mkdir -p "$A5_ROOT/codex_output" "$A5_ROOT/logs" "$A5_ROOT/temporary/pycache"

if [ ! -d "$A5_ROOT/test_clone/08.18.26_Level1_Audits_R8" ]; then
  echo "RUNNER_FAIL: the disposable test clone is absent" >&2
  exit 2
fi
if [ ! -f "$A5_ROOT/original_inventory/INVENTORY_PRE.json" ]; then
  echo "RUNNER_FAIL: the pre-verification inventory is absent" >&2
  exit 2
fi
if [ ! -f "$A5_ROOT/TOOL_INVENTORY.json" ]; then
  echo "RUNNER_FAIL: the tool inventory is absent" >&2
  exit 2
fi

{
  echo "runner_started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "codex_version=$(codex --version)"
  echo "workspace_root=$A5_ROOT"
  echo "r8_root_readonly=$R8_ROOT"
  echo "prompt_sha256=$(/usr/bin/sha256sum "$PROMPT_FILE" | cut -d' ' -f1)"
} > "$A5_ROOT/logs/runner_context.txt"

# The prompt is passed on stdin so no part of it is subject to shell
# expansion. --skip-git-repo-check because ATTEMPT5_ROOT is not a git
# repository and must not become one.
codex exec \
  --sandbox workspace-write \
  -C "$A5_ROOT" \
  --skip-git-repo-check \
  - < "$PROMPT_FILE" \
  > "$A5_ROOT/logs/codex_attempt_5.stdout.txt" \
  2> "$A5_ROOT/logs/codex_attempt_5.stderr.txt"

status=$?
echo "codex_exit_status=$status" >> "$A5_ROOT/logs/runner_context.txt"
echo "runner_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> "$A5_ROOT/logs/runner_context.txt"
exit $status
