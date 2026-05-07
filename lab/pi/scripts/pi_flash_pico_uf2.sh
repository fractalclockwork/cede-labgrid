#!/usr/bin/env bash
# Copy a UF2 to a Pico in BOOTSEL mass-storage mode (RPI-RP2). Run ON the Raspberry Pi gateway.
#
# Usage:
#   ./pi_flash_pico_uf2.sh --uf2 /path/hello.uf2 --yes
#   ./pi_flash_pico_uf2.sh --uf2 /path/hello.uf2 --mount /media/$USER/RPI-RP2 --yes
#
# Without --mount, searches /media/*/RPI-RP2 and /run/media/*/RPI-RP2.

set -euo pipefail

usage() {
  sed -n '1,14p' "$0"
  exit "${1:-0}"
}

UF2=""
MOUNT=""
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uf2)
      UF2="${2:?}"
      shift 2
      ;;
    --mount)
      MOUNT="${2:?}"
      shift 2
      ;;
    --yes)
      YES=1
      shift
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage 1
      ;;
  esac
done

if [[ "${YES}" -ne 1 ]]; then
  echo "refusing: pass --yes after confirming Pico is in BOOTSEL and mount is correct" >&2
  exit 1
fi

if [[ -z "${UF2}" ]] || [[ ! -f "${UF2}" ]]; then
  echo "error: --uf2 must name an existing file" >&2
  exit 1
fi

find_rpi_rp2_mount() {
  local d
  for d in /media/*/"RPI-RP2" /run/media/*/"RPI-RP2"; do
    if [[ -d "$d" ]]; then
      if command -v mountpoint >/dev/null 2>&1; then
        mountpoint -q "$d" 2>/dev/null || continue
      fi
      echo "$d"
      return 0
    fi
  done
  return 1
}

if [[ -z "${MOUNT}" ]]; then
  MOUNT="$(find_rpi_rp2_mount)" || true
fi

if [[ -z "${MOUNT}" ]] || [[ ! -d "${MOUNT}" ]]; then
  echo "error: BOOTSEL volume RPI-RP2 not mounted. Hold BOOTSEL, plug Pico USB, then retry." >&2
  echo "       Or pass --mount /full/path/to/RPI-RP2" >&2
  exit 1
fi

echo "==> Copy $(basename "${UF2}") -> ${MOUNT}"
cp -v "${UF2}" "${MOUNT}/"
sync
echo "==> Done. Pico should reboot; RPI-RP2 may disappear."
