#!/usr/bin/env bash
# Legacy entrypoint — delegates to bootstrap/bootstrap_pi.sh
exec "$(cd "$(dirname "$0")" && pwd)/bootstrap/bootstrap_pi.sh" "$@"
