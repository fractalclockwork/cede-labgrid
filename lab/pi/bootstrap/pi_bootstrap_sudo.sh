#!/usr/bin/env bash
# Run pi_bootstrap.py with elevated privileges using the repo .venv Python.
# `sudo uv run ...` often fails because sudo's PATH omits ~/.local/bin where uv lives.
#
# Usage (from repo root):
#   ./lab/pi/bootstrap/pi_bootstrap_sudo.sh flash-file --device /dev/sdc --image lab/pi/dist/foo.img --yes
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "error: $PY not found — run: cd \"$ROOT\" && uv sync" >&2
  exit 1
fi
exec sudo "$PY" "$ROOT/lab/pi/bootstrap/pi_bootstrap.py" "$@"
