#!/usr/bin/env bash
# Create the disposable package clone as a DIRECT SIBLING of R8.
#
# The placement is the whole point. `paths.json` is location-relative, so the
# package carries its roots with it:
#
#     project_root    ".."                          -> the clone's parent
#     discovery_root  "../08.18.26_Discovery"       -> a sibling of the clone
#     level1_root     "."                           -> the clone
#
# Put the clone anywhere but beside R8 and those three resolve to a directory
# that holds nothing, a Discovery root that does not exist, and a project root
# with no predecessor packages under it. That is attempt 5's defect. Put it
# beside R8 and all three resolve to the real architecture, while every write
# is still absorbed by the clone, because WRITE_ROOTS = (LEVEL1_ROOT,).
#
# The name is hidden and does not match the revision glob
# `08.18.26_Level1_Audits*`, so no tool that enumerates revisions can mistake
# the clone for one.
#
# cp -a --reflink=auto: byte-preserving, metadata-preserving, and never a
# hardlink to the source. A hardlink would make a write to the clone a write
# to R8, which is exactly what this whole apparatus exists to prevent.
set -u -o pipefail

R8_ROOT="/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
PROJECT_ROOT="/home/ubuntu/project/WPNO"
CLONE="$PROJECT_ROOT/.r8_verify_clone_attempt_8_$$"

case "$CLONE" in
  "$PROJECT_ROOT"/*) : ;;
  *) echo "CLONE_FAIL: clone would fall outside PROJECT_ROOT" >&2; exit 2 ;;
esac
if [ -e "$CLONE" ]; then
  echo "CLONE_FAIL: $CLONE already exists" >&2; exit 2
fi

cp -a --reflink=auto "$R8_ROOT" "$CLONE" || { echo "CLONE_FAIL: copy failed" >&2; exit 2; }
echo "$CLONE"
