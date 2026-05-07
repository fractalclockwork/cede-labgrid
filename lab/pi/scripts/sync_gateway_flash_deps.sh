#!/usr/bin/env bash
# Push only the Pi-side files needed for `make -C lab/pi` flash helpers (no firmware, no Docker, no full tree).
#
# Usage:
#   ./sync_gateway_flash_deps.sh user@cede-pi.local
#   ./sync_gateway_flash_deps.sh user@cede-pi.local /path/on/pi/cede   # optional explicit remote dir (-- dest)
#   UNO_ONLY=1 ./sync_gateway_flash_deps.sh user@cede-pi.local        # skip Pico UF2 script if you only flash Uno

set -euo pipefail

usage() {
  sed -n '1,10p' "$0"
  exit "${1:-0}"
}

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  usage 0
fi

REMOTE="${1:?user@host required (see --help)}"
# Do not use ${2:-~/cede}: bash expands ~ in the default word to THIS machine's home, so rsync
# would try to create /home/<dev_user>/cede on the Pi and fail.
if [[ $# -ge 2 ]]; then
  RDIR_RAW="$2"
else
  RDIR_RAW='~/cede'
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

cd "${REPO_ROOT}"

# Create base on the gateway (tilde must expand on the receiver, not locally).
if [[ "${RDIR_RAW}" =~ ^~(/|$) ]]; then
  # shellcheck disable=SC2029
  ssh "${REMOTE}" "mkdir -p ${RDIR_RAW}"
else
  # shellcheck disable=SC2029
  ssh "${REMOTE}" "mkdir -p $(printf '%q' "${RDIR_RAW}")"
fi

FILES=(
  lab/pi/Makefile
  lab/pi/scripts/health_check.py
  lab/pi/scripts/pi_flash_uno_avrdude.sh
  lab/pi/scripts/pi_resolve_gateway_uno.py
  lab/pi/scripts/pi_validate_uno_serial.py
)
if [[ "${UNO_ONLY:-}" != "1" ]]; then
  FILES+=(lab/pi/scripts/pi_flash_pico_uf2.sh)
fi

rsync -avz \
  --human-readable \
  -e ssh \
  -R \
  "${FILES[@]}" \
  "${REMOTE}:${RDIR_RAW}"
