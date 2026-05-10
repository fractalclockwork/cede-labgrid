#!/usr/bin/env bash
# Push only the Pi-side files needed for `make -C lab/pi` flash helpers (no firmware, no Docker).
# The gateway must NOT hold a full CEDE git checkout — only this rsync tree (default ~/cede/lab/pi/…).
#
# Usage:
#   ./sync_gateway_flash_deps.sh user@cede-pi.local
#   ./sync_gateway_flash_deps.sh user@cede-pi.local /path/on/pi/cede   # optional explicit remote dir (-- dest)
#   UNO_ONLY=1 ./sync_gateway_flash_deps.sh user@cede-pi.local        # skip all Pico (cede-rp2) helpers; Uno-only sync

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
  lab/pi/ssd1306_dual/main.py
  lab/pi/ssd1306_dual/bus_speed_test.py
  lab/pi/ssd1306_dual/requirements.txt
  lab/pi/ssd1306_dual/cede_app.yaml
  lab/pi/ssd1306_dual/README.md
  lab/pi/ssd1306_eyes/main.py
  lab/pi/ssd1306_eyes/eyes_anim.py
  lab/pi/ssd1306_eyes/eyes_draw.py
  lab/pi/ssd1306_eyes/dirty_stats.py
  lab/pi/ssd1306_eyes/requirements.txt
  lab/pi/ssd1306_eyes/cede_app.yaml
  lab/pi/ssd1306_eyes/README.md
  lab/pi/scripts/health_check.py
  lab/pi/scripts/pi_flash_uno_avrdude.sh
  lab/pi/scripts/pi_resolve_gateway_uno.py
  lab/pi/scripts/pi_validate_uno_serial.py
  lab/pi/scripts/cede_firmware_attest.py
  lab/pi/scripts/pi_validate_gateway_native.py
  lab/pi/scripts/lab_i2c_matrix_validate.py
)
if [[ "${UNO_ONLY:-}" != "1" ]]; then
  FILES+=(
    lab/pi/scripts/pi_flash_pico_mount_lib.sh
    lab/pi/scripts/pi_flash_pico_uf2.sh
    lab/pi/scripts/pi_flash_pico_auto.sh
    lab/pi/scripts/pi_resolve_gateway_pico.py
    lab/pi/scripts/pi_validate_pico_serial.py
  )
fi

rsync -avz \
  --human-readable \
  -e ssh \
  -R \
  "${FILES[@]}" \
  "${REMOTE}:${RDIR_RAW}"

echo "==> gateway flash deps synced to ${REMOTE}:${RDIR_RAW}"
echo "    Pi gateway: sparse tree only — no git clone; firmware and aarch64 hello_gateway are copied from the Dev-Host (scp)."
