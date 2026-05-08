#!/usr/bin/env bash
# Copy a UF2 to a Pico in BOOTSEL mass-storage mode (RPI-RP2). Run ON the Raspberry Pi gateway.
#
# Usage:
#   ./pi_flash_pico_uf2.sh --uf2 /path/hello.uf2 --yes
#   ./pi_flash_pico_uf2.sh --uf2 /path/hello.uf2 --mount /media/$USER/RPI-RP2 --yes
#
# Without --mount, resolves /media/*/RPI-RP2, /run/media/*/RPI-RP2, or /dev/disk/by-label/RPI-RP2 (udisks mount).

set -euo pipefail

_PI_FLASH_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pi_flash_pico_mount_lib.sh"
if [[ ! -f "${_PI_FLASH_LIB}" ]]; then
  echo "error: missing ${_PI_FLASH_LIB}" >&2
  exit 1
fi
# shellcheck source=pi_flash_pico_mount_lib.sh
source "${_PI_FLASH_LIB}"

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

if [[ -z "${MOUNT}" ]]; then
  MOUNT="$(find_rpi_rp2_mount)" || true
fi

if [[ -z "${MOUNT}" ]] || [[ ! -d "${MOUNT}" ]]; then
  echo "note: no mount point; trying verified raw RPI-RP2 partition write …" >&2
  if try_fallback_uf2_to_rpi_rp2_partition "${UF2}" 15; then
    echo "==> Done. Pico should reboot; RPI-RP2 may disappear."
    exit 0
  fi
  echo "error: BOOTSEL volume RPI-RP2 not found. Hold BOOTSEL, plug Pico USB, then retry." >&2
  echo "       Or pass --mount /full/path/to/RPI-RP2" >&2
  exit 1
fi

echo "==> Copy $(basename "${UF2}") -> ${MOUNT}"
cp -v "${UF2}" "${MOUNT}/"
sync
echo "==> Done. Pico should reboot; RPI-RP2 may disappear."
