#!/bin/sh
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
if [ "$#" -ne 2 ]; then /bin/echo "Usage: $0 ABSOLUTE_EXTERNAL_LAUNCH_DIRECTORY ABSOLUTE_OUTPUT_DIRECTORY" >&2; exit 64; fi
launch_arg=$1
output_arg=$2
case "$launch_arg" in /*) ;; *) /bin/echo "Launch directory must be absolute" >&2; exit 64;; esac
case "$output_arg" in /*) ;; *) /bin/echo "Output directory must be absolute" >&2; exit 64;; esac
if [ -L "$output_arg" ]; then /bin/echo "Output directory must not be a symlink" >&2; exit 65; fi
if [ ! -d "$output_arg" ]; then /bin/mkdir -p "$output_arg"; fi
output_real=$(/usr/bin/realpath "$output_arg")
if [ -e "$launch_arg" ]; then launch_real=$(/usr/bin/realpath "$launch_arg"); else launch_real=$launch_arg; fi
case "$output_real" in "$launch_real"|"$launch_real"/*) /bin/echo "Output must be separate from launch directory" >&2; exit 65;; esac
report="$output_real/host_and_paths.txt"
manifest="$output_real/launch_directory_files.sha256"
: > "$report"
: > "$manifest"
{
  /bin/echo "capture_utc=$(/bin/date -u +%Y-%m-%dT%H:%M:%SZ)"
  /bin/echo "hostname=$(/bin/hostname)"
  /usr/bin/sw_vers
  /bin/echo "hardware_uuid=$(/usr/sbin/ioreg -rd1 -c IOPlatformExpertDevice | /usr/bin/awk -F\" '/IOPlatformUUID/{print $4}')"
  /bin/echo "canonical_HOME=$(/usr/bin/realpath "$HOME")"
  /bin/echo "launch_argument=$launch_arg"
  /bin/echo "launch_canonical=$launch_real"
  if [ -L "$launch_arg" ]; then /bin/echo 'launch_is_symlink=YES'; else /bin/echo 'launch_is_symlink=NO'; fi
  if [ -e "$launch_arg" ]; then /bin/echo 'launch_exists=YES'; else /bin/echo 'launch_exists=NO'; fi
} >> "$report"
record_file() {
  p=$1
  label=$2
  {
    /bin/echo "[$label]"
    /bin/echo "path=$p"
    if [ -L "$p" ]; then /bin/echo 'symlink=YES'; return; else /bin/echo 'symlink=NO'; fi
    if [ -e "$p" ]; then
      /bin/echo 'exists=YES'
      /usr/bin/stat -f 'type=%HT size=%z' "$p"
      if [ -f "$p" ]; then /bin/echo "sha256=$(/usr/bin/shasum -a 256 "$p" | /usr/bin/awk '{print $1}')"; fi
    else /bin/echo 'exists=NO'; fi
  } >> "$report"
}
record_file "$HOME/.claude/CLAUDE.md" user_CLAUDE_md
record_file "/Users/martinotten/WPNO/CLAUDE.md" project_CLAUDE_md_required_by_L1_A23
if [ -L "$launch_arg" ]; then /bin/echo 'Refusing symlink launch directory' >&2; exit 66; fi
if [ -d "$launch_arg" ]; then
  /usr/bin/find -s -x "$launch_arg" -type l -print > "$output_real/launch_directory_symlinks.txt"
  /usr/bin/find -s -x "$launch_arg" -type f -print | while IFS= read -r f; do /usr/bin/shasum -a 256 "$f"; done > "$manifest"
fi
{
  /bin/echo '[expected_CLAUDE_resolution]'
  d=$launch_real
  while :; do /bin/echo "$d/CLAUDE.md"; [ "$d" = / ] && break; d=$(/usr/bin/dirname "$d"); done
  /bin/echo "$HOME/.claude/CLAUDE.md"
} >> "$report"
/bin/echo "Read-only capture complete: $output_real"
