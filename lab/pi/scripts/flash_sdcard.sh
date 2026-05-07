#!/usr/bin/env bash
# Flash Raspberry Pi OS to an SD card / USB reader using rpi-imager --cli, then optionally
# copy rendered cloud-init files onto the boot (FAT) partition.
#
# Usage:
#   sudo ./flash_sdcard.sh --device /dev/mmcblk0 --url <file-or-https-url> --yes \
#       [--hostname cede-gateway] [--sha256 <hash>] \
#       [--authorized-keys ~/.ssh/id_ed25519.pub] [--ssh-user pi]
#   sudo ./flash_sdcard.sh ... --yes --use-existing-rendered
#       (skip re-render; copy lab/pi/cloud-init/rendered after pi_bootstrap.py render)
# If the card is already flashed (e.g. Imager GUI), use prepare_sdcard_boot.sh instead of re-flashing.
#
# Requires: rpi-imager (apt install rpi-imager), util-linux (mount), coreutils.
#
# Safety: you must pass --yes after confirming --device is the correct removable disk.
# Run with sudo when prompted; interactive sudo is fine—no passwordless automation required.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib_sdcard.sh
source "${SCRIPT_DIR}/lib_sdcard.sh"

usage() {
  sed -n '1,25p' "$0"
  exit "${1:-0}"
}

DEVICE=""
IMAGE_URI=""
SHA256=""
HOSTNAME=""
YES=0
AUTHORIZED_KEYS=""
SSH_USER="pi"
USE_EXISTING_RENDERED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --device)
      DEVICE="${2:?}"
      shift 2
      ;;
    --url)
      IMAGE_URI="${2:?}"
      shift 2
      ;;
    --sha256)
      SHA256="${2:?}"
      shift 2
      ;;
    --hostname)
      HOSTNAME="${2:?}"
      shift 2
      ;;
    --authorized-keys)
      AUTHORIZED_KEYS="${2:?}"
      shift 2
      ;;
    --ssh-user)
      SSH_USER="${2:?}"
      shift 2
      ;;
    --yes)
      YES=1
      shift
      ;;
    --use-existing-rendered)
      USE_EXISTING_RENDERED=1
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

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo $0 ..." >&2
  exit 1
fi

if [[ -z "${DEVICE}" ]] || [[ -z "${IMAGE_URI}" ]]; then
  echo "error: --device and --url are required" >&2
  usage 1
fi

if [[ "${YES}" -ne 1 ]]; then
  echo "error: refusing to write without --yes (confirm SD device is correct)" >&2
  exit 1
fi

if ! command -v rpi-imager >/dev/null 2>&1; then
  echo "error: rpi-imager not found; install with: sudo apt install rpi-imager" >&2
  exit 1
fi

[[ -b "${DEVICE}" ]] || {
  echo "error: not a block device: ${DEVICE}" >&2
  exit 1
}

if [[ -n "${AUTHORIZED_KEYS}" ]] && [[ ! -f "${AUTHORIZED_KEYS}" ]]; then
  echo "error: --authorized-keys is not a readable file: ${AUTHORIZED_KEYS}" >&2
  exit 1
fi

REPO_ROOT="$(cede_repo_root_from_scripts)"

echo "==> Flashing ${IMAGE_URI} -> ${DEVICE}"
CLI_ARGS=(--cli)
[[ -n "${SHA256}" ]] && CLI_ARGS+=(--sha256 "${SHA256}")

# Detach from TTY: rpi-imager --cli can otherwise sit at 100% with a <defunct> child while
# sudo stays in the foreground (Qt / console handling). Non-interactive flash does not need stdin.
rpi-imager "${CLI_ARGS[@]}" "${IMAGE_URI}" "${DEVICE}" </dev/null

if [[ "${USE_EXISTING_RENDERED}" -eq 1 ]]; then
  echo "==> Copying pre-rendered cloud-init from lab/pi/cloud-init/rendered/"
  if ! cede_wait_for_boot_partition "${DEVICE}"; then
    BOOT="$(cede_boot_partition "${DEVICE}")"
    echo "warn: boot partition not found at ${BOOT} after wait; skip cloud-init copy. Try: unplug/replug the reader, run sudo partprobe ${DEVICE}, or prepare_sdcard_boot.sh (see lab/pi/docs/cli-flash.md)" >&2
    exit 0
  fi
  cede_cloud_init_copy_to_boot_partition "${DEVICE}" "${REPO_ROOT}"
elif [[ -n "${HOSTNAME}" ]]; then
  echo "==> Rendering cloud-init for hostname ${HOSTNAME}"
  cede_render_cloud_init "${REPO_ROOT}" "${HOSTNAME}" "${AUTHORIZED_KEYS}" "${SSH_USER}"
  if ! cede_wait_for_boot_partition "${DEVICE}"; then
    BOOT="$(cede_boot_partition "${DEVICE}")"
    echo "warn: boot partition not found at ${BOOT} after wait; skip cloud-init copy. Try: unplug/replug the reader, sudo partprobe ${DEVICE}, or prepare_sdcard_boot.sh (see lab/pi/docs/cli-flash.md)" >&2
    exit 0
  fi
  cede_cloud_init_copy_to_boot_partition "${DEVICE}" "${REPO_ROOT}"
else
  if ! cede_wait_for_boot_partition "${DEVICE}"; then
    BOOT="$(cede_boot_partition "${DEVICE}")"
    echo "warn: boot partition not found at ${BOOT} after wait; skip cloud-init copy. Try: unplug/replug the reader, sudo partprobe ${DEVICE}, or prepare_sdcard_boot.sh (see lab/pi/docs/cli-flash.md)" >&2
    exit 0
  fi
  echo "==> No --hostname; skipped cloud-init. Render later with lab/pi/bootstrap/render_cloud_init.sh and copy files (cli-flash.md)."
fi

echo "Done. Safe to eject ${DEVICE}."
