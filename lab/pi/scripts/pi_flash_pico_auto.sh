#!/usr/bin/env bash
# cede-rp2: Flash UF2 from the Raspberry Pi gateway — try picotool reboot -uf into BOOTSEL, then copy to RPI-RP2.
#
# Usage:
#   ./pi_flash_pico_auto.sh --uf2 /path/hello.uf2 --yes
#   ./pi_flash_pico_auto.sh --uf2 /path/hello.uf2 --yes --bootsel-only   # skip picotool; Pico already in BOOTSEL
#   ./pi_flash_pico_auto.sh --uf2 /path/hello.uf2 --yes --wait-mount 30   # slow desktop automount
#
# Requires a picotool built WITH USB support for reboot (typical Raspberry Pi OS apt package).
# Docker pico-dev picotool is often built without USB — use --bootsel-only there or flash from the Pi.

set -euo pipefail

_PI_FLASH_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pi_flash_pico_mount_lib.sh"
if [[ ! -f "${_PI_FLASH_LIB}" ]]; then
  echo "error: missing ${_PI_FLASH_LIB}" >&2
  exit 1
fi
# shellcheck source=pi_flash_pico_mount_lib.sh
source "${_PI_FLASH_LIB}"

usage() {
  sed -n '1,18p' "$0"
  exit "${1:-0}"
}

UF2=""
YES=0
BOOTSEL_ONLY=0
# How long to poll for RPI-RP2 automount (udisks). Headless gateways usually never mount; fallback raw write is fast.
WAIT_MOUNT=3

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uf2)
      UF2="${2:?}"
      shift 2
      ;;
    --yes)
      YES=1
      shift
      ;;
    --bootsel-only)
      BOOTSEL_ONLY=1
      shift
      ;;
    --wait-mount)
      WAIT_MOUNT="${2:?}"
      shift 2
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
  echo "refusing: pass --yes after confirming UF2 path and gateway state" >&2
  exit 1
fi

if [[ -z "${UF2}" ]] || [[ ! -f "${UF2}" ]]; then
  echo "error: --uf2 must name an existing file" >&2
  exit 1
fi

picotool_has_reboot() {
  command -v picotool >/dev/null 2>&1 && picotool help 2>&1 | grep -qE '[[:space:]]reboot[[:space:]]'
}

try_picotool_reboot_usb_boot() {
  if ! picotool_has_reboot; then
    echo "note: picotool has no 'reboot' command (USB support missing). Use --bootsel-only or install full picotool on the Pi." >&2
    return 1
  fi
  # -u: USB boot (BOOTSEL). -f: force when runtime firmware is USB serial (e.g. MicroPython), where plain -u fails.
  echo "==> picotool reboot -uf (enter USB boot / UF2 disk)"
  picotool reboot -uf || return 1
}

wait_for_rpi_rp2() {
  local deadline=$((SECONDS + WAIT_MOUNT))
  local m=""
  while (( SECONDS < deadline )); do
    m="$(find_rpi_rp2_mount)" || true
    if [[ -n "${m}" ]]; then
      echo "${m}"
      return 0
    fi
    sleep 0.4
  done
  return 1
}

MOUNT=""
if m0="$(find_rpi_rp2_mount)"; then
  MOUNT="${m0}"
  echo "==> RPI-RP2 already mounted at ${MOUNT}"
else
  if [[ "${BOOTSEL_ONLY}" -eq 1 ]]; then
    echo "==> BOOTSEL-only: waiting up to ${WAIT_MOUNT}s for RPI-RP2 …"
  else
    if try_picotool_reboot_usb_boot; then
      echo "==> waiting up to ${WAIT_MOUNT}s for RPI-RP2 mount …"
    else
      echo "error: could not enter BOOTSEL via picotool. Hold BOOTSEL, plug Pico, or pass --bootsel-only." >&2
      exit 1
    fi
  fi

  if ! MOUNT="$(wait_for_rpi_rp2)"; then
    echo "note: no RPI-RP2 mount within ${WAIT_MOUNT}s; trying verified raw partition write …" >&2
    if try_fallback_uf2_to_rpi_rp2_partition "${UF2}" 15; then
      echo "==> Done. Pico should reboot; RPI-RP2 may disappear."
      exit 0
    fi
    echo "error: RPI-RP2 volume did not appear within ${WAIT_MOUNT}s." >&2
    echo "       On the Pi: lsblk -o PATH,LABEL; blkid; ls -l /dev/disk/by-label/" >&2
    echo "       Hold BOOTSEL while connecting USB, then retry with --bootsel-only if picotool is unavailable." >&2
    exit 1
  fi
fi

echo "==> Copy $(basename "${UF2}") -> ${MOUNT}"
cp -v "${UF2}" "${MOUNT}/"
sync
echo "==> Done. Pico should reboot; RPI-RP2 may disappear."
