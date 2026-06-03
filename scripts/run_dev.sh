#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  python_bin="$VIRTUAL_ENV/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
else
  python_bin="$(command -v python)"
fi

workspace_root="$repo_root/workspace"
output_root="$repo_root/output"

mkdir -p "$workspace_root" "$output_root"

: "${WORKSPACE_ROOT:=$workspace_root}"
: "${OUTPUT_ROOT:=$output_root}"
export WORKSPACE_ROOT OUTPUT_ROOT

exec "$python_bin" -m markitdesk.app
