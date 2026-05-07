#!/usr/bin/env bash
# Attach a loop device to a Raspberry Pi OS .img (or raw disk image), mount the first
# partition (FAT boot), inject rendered cloud-init from the repo, then detach.
#
# Usage:
#   sudo ./patch_image_boot.sh --image ./raspios-lite-arm64.img --yes
#
# Requires: util-linux (losetup, mount), coreutils. Run render_cloud_init first (or pi_bootstrap.py render).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib_sdcard.sh
source "${SCRIPT_DIR}/lib_sdcard.sh"

usage() {
  sed -n '1,15p' "$0"
  exit "${1:-0}"
}

IMAGE=""
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)
      IMAGE="${2:?}"
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

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo $0 ..." >&2
  exit 1
fi

if [[ -z "${IMAGE}" ]]; then
  echo "error: --image is required" >&2
  usage 1
fi

if [[ "${YES}" -ne 1 ]]; then
  echo "error: refusing without --yes (confirm image path is correct)" >&2
  exit 1
fi

[[ -f "${IMAGE}" ]] || {
  echo "error: not a file: ${IMAGE}" >&2
  exit 1
}

REPO_ROOT="$(cede_repo_root_from_scripts)"
LOOP=""
MNT="$(mktemp -d)"

cleanup() {
  umount -lf "${MNT}" 2>/dev/null || true
  if [[ -n "${LOOP}" ]] && losetup "${LOOP}" >/dev/null 2>&1; then
    losetup -d "${LOOP}" 2>/dev/null || true
  fi
  rmdir "${MNT}" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Loop-mount ${IMAGE}"
LOOP="$(losetup -f --show -Pf "${IMAGE}")"
BOOT="${LOOP}p1"

if [[ ! -b "${BOOT}" ]]; then
  echo "error: expected boot partition at ${BOOT}; layout may differ from Raspberry Pi OS images" >&2
  exit 1
fi

echo "==> Mounting ${BOOT}"
mount "${BOOT}" "${MNT}"

cede_cloud_init_copy_to_boot_mount "${MNT}" "${REPO_ROOT}"

if command -v blockdev >/dev/null 2>&1; then
  blockdev --flushbufs "${LOOP}" 2>/dev/null || true
fi

umount "${MNT}"
losetup -d "${LOOP}"
LOOP=""
trap - EXIT
rmdir "${MNT}"

echo "Done. Flash once with: sudo rpi-imager --cli ... \"${IMAGE}\" /dev/sdX"
