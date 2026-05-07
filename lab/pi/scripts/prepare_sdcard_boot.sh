#!/usr/bin/env bash
# After manually flashing an image (e.g. rpi-imager GUI), mount the boot FAT partition,
# inject rendered cloud-init, flush buffers, and umount — no re-flash.
#
# Usage:
#   sudo ./prepare_sdcard_boot.sh --device /dev/sdc --hostname cede-gateway --yes \
#       [--authorized-keys ~/.ssh/id_ed25519.pub] [--ssh-user pi]
#   sudo ./prepare_sdcard_boot.sh --device /dev/sdc --yes --use-existing-rendered
#       (skip re-render; copy lab/pi/cloud-init/rendered after pi_bootstrap.py render)
#
# Requires: util-linux (mount), coreutils. Same safety pattern as flash_sdcard.sh (--yes).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib_sdcard.sh
source "${SCRIPT_DIR}/lib_sdcard.sh"

usage() {
  sed -n '1,20p' "$0"
  exit "${1:-0}"
}

DEVICE=""
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

if [[ -z "${DEVICE}" ]]; then
  echo "error: --device is required" >&2
  usage 1
fi

if [[ "${USE_EXISTING_RENDERED}" -ne 1 ]] && [[ -z "${HOSTNAME}" ]]; then
  echo "error: --hostname is required unless --use-existing-rendered" >&2
  usage 1
fi

if [[ "${YES}" -ne 1 ]]; then
  echo "error: refusing without --yes (confirm SD device is correct)" >&2
  exit 1
fi

[[ -b "${DEVICE}" ]] || {
  echo "error: not a block device: ${DEVICE}" >&2
  exit 1
}

REPO_ROOT="$(cede_repo_root_from_scripts)"

if [[ -n "${AUTHORIZED_KEYS}" ]] && [[ ! -f "${AUTHORIZED_KEYS}" ]]; then
  echo "error: --authorized-keys is not a readable file: ${AUTHORIZED_KEYS}" >&2
  exit 1
fi

if [[ "${USE_EXISTING_RENDERED}" -eq 1 ]]; then
  echo "==> Copying pre-rendered cloud-init from lab/pi/cloud-init/rendered/"
  if ! cede_wait_for_boot_partition "${DEVICE}"; then
    BOOT="$(cede_boot_partition "${DEVICE}")"
    echo "error: boot partition not found at ${BOOT}; replug USB reader and check lsblk ${DEVICE}" >&2
    exit 1
  fi
  cede_cloud_init_copy_to_boot_partition "${DEVICE}" "${REPO_ROOT}"
else
  cede_cloud_init_install_to_sdcard "${DEVICE}" "${REPO_ROOT}" "${HOSTNAME}" "${AUTHORIZED_KEYS}" "${SSH_USER}"
fi

echo "Done. Safe to eject ${DEVICE}."
