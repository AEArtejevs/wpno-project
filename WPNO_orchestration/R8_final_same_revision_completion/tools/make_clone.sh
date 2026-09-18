#!/usr/bin/env bash
# The disposable package clone, placed as a DIRECT SIBLING of R8.
#
# `paths.json` is location-relative, so the package carries its roots with it:
# project_root "..", discovery_root "../08.18.26_Discovery", level1_root ".".
# Beside R8 those resolve to the real project root, the real Discovery root and
# the real predecessor siblings, while every write is still absorbed by the
# clone, because WRITE_ROOTS = (LEVEL1_ROOT,). Anywhere else and the package
# resolves a project root that holds nothing.
#
# The name is hidden and does not match `08.18.26_Level1_Audits*`, so nothing
# that enumerates revisions can mistake the clone for one.
#
# `-e` as well as `-u -o pipefail`: this package's static-safety review requires
# it, and every failure path below already exits explicitly.
set -e -u -o pipefail

R8_ROOT="/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8"
PROJECT_ROOT="/home/ubuntu/project/WPNO"
CLONE="$PROJECT_ROOT/.r8_lineage_verify_clone_$$"

case "$CLONE" in
  "$PROJECT_ROOT"/*) : ;;
  *) echo "CLONE_FAIL: clone would fall outside PROJECT_ROOT" >&2; exit 2 ;;
esac
if [ -e "$CLONE" ]; then
  echo "CLONE_FAIL: $CLONE already exists" >&2; exit 2
fi

# byte- and metadata-preserving, and never a hardlink to the source: a hardlink
# would make a write to the clone a write to R8.
cp -a --reflink=auto "$R8_ROOT" "$CLONE" || {
  echo "CLONE_FAIL: copy failed" >&2; exit 2; }
echo "$CLONE"
