#!/usr/bin/env bash
# Write a raw disk image or hybrid ISO to a whole block device using dd.
#
# Works for any byte-for-byte boot media layout the distributor describes as "write with dd":
#   • Raspberry Pi OS .img (after xz decompress; see: make pi-raw-sd-image)
#   • Many Linux live/install **hybrid ISOs** (Ubuntu, Debian installer ISOs marked isohybrid / dd-able)
#   • Raw cloud / appliance **.img** dumps (verify upstream docs before assuming dd safety)
#   • USB thumb drives, SD readers, SATA/NVMe/USB enclosures appearing as /dev/sdX or /dev/nvme*n*
#
# Does NOT replace distro-specific tools when the artifact is not dd-safe (some Windows images,
# non-hybrid ISOs that expect FAT copy — follow vendor docs).
#
# Usage:
#   sudo ./flash_raw_to_device.sh --device /dev/sdX --image /path/to/file.img --yes
#   sudo ./flash_raw_to_device.sh --device /dev/nvme0n1 --image ~/Downloads/debian-live-amd64.iso --yes
#
# Safety:
#   --device must be the whole block device, not a partition (see lsblk).
#   Pass --yes only after confirming DEVICE with lsblk/fdisk (wrong target destroys data).
# Environment:
#   CEDE_DD_DELAY_SEC=0 — skip pre-write delay
#   CEDE_DD_NO_FSYNC=1 — if dd fails with "fsync failed ... Input/output error", omit conv=fsync

set -euo pipefail

usage() {
  sed -n '1,35p' "$0"
  exit "${1:-0}"
}

DEVICE=""
IMAGE=""
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --device)
      DEVICE="${2:?}"
      shift 2
      ;;
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

if [[ "${YES}" -ne 1 ]]; then
  echo "refusing: pass --yes after confirming --device is the correct whole-disk device." >&2
  exit 1
fi

if [[ -z "${DEVICE}" || -z "${IMAGE}" ]]; then
  echo "usage: sudo $0 --device /dev/sdX --image path/to.img_or_hybrid.iso --yes" >&2
  exit 1
fi

if [[ ! -b "${DEVICE}" ]]; then
  echo "error: not a block device: ${DEVICE}" >&2
  exit 1
fi

if [[ ! -f "${IMAGE}" ]]; then
  echo "error: image not found: ${IMAGE}" >&2
  exit 1
fi

if [[ "${DEVICE}" =~ mmcblk.*p[0-9]+$ ]] || [[ "${DEVICE}" =~ nvme[0-9]+n[0-9]+p[0-9]+$ ]] || [[ "${DEVICE}" =~ sd[a-z]+[0-9]+$ ]]; then
  echo "error: use whole disk (e.g. /dev/sdc or /dev/nvme0n1), not a partition: ${DEVICE}" >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "error: run as root (sudo) to write to ${DEVICE}" >&2
  exit 1
fi

# Verify CEDE payload exists in Pi .img before destructive dd.
# Set CEDE_SKIP_CLOUDINIT_CHECK=1 to bypass for generic images/ISOs.
if [[ "${CEDE_SKIP_CLOUDINIT_CHECK:-0}" != "1" ]] && [[ "${IMAGE}" == *.img ]]; then
  LOOP=""
  MNT="$(mktemp -d)"
  cleanup_preflight() {
    umount -lf "${MNT}" 2>/dev/null || true
    if [[ -n "${LOOP}" ]]; then
      losetup -d "${LOOP}" 2>/dev/null || true
    fi
    rmdir "${MNT}" 2>/dev/null || true
  }
  trap cleanup_preflight EXIT

  LOOP="$(losetup -f --show -Pf "${IMAGE}")"
  BOOT="${LOOP}p1"
  if [[ -b "${BOOT}" ]]; then
    mount -o ro "${BOOT}" "${MNT}"
    HAS_CEDE=0
    # CEDE-patched gateway images include enable_ssh + hostname and do not ship the generic cloud-init ubuntu template blob.
    if [[ -f "${MNT}/user-data" ]] \
      && grep -q 'enable_ssh:[[:space:]]*true' "${MNT}/user-data" \
      && grep -qE '^hostname:[[:space:]]+[^[:space:]#]+' "${MNT}/user-data" \
      && ! grep -Fq 'initial user called "ubuntu"' "${MNT}/user-data"; then
      HAS_CEDE=1
    fi
    if [[ "${HAS_CEDE}" -ne 1 ]]; then
      echo "error: ${IMAGE} boot partition does not appear to contain CEDE rendered cloud-init user-data." >&2
      echo "       Refusing to flash to prevent writing an unpatched image." >&2
      echo "       Run: make pi-bootstrap-render && make pi-gateway-img-patch IMG=${IMAGE}" >&2
      echo "       If this is intentional (generic image), set CEDE_SKIP_CLOUDINIT_CHECK=1." >&2
      exit 1
    fi
  fi
  cleanup_preflight
  trap - EXIT
fi

DELAY_SEC="${CEDE_DD_DELAY_SEC:-5}"

# Default conv=fsync ensures data hits the medium before dd exits. Some USB readers or SD cards
# return EIO on the final fsync (you still see "dd: fsync failed"). Set CEDE_DD_NO_FSYNC=1 to
# omit fsync here and rely on explicit sync below (retry flash or another port/card if sync fails).
_CONV=(conv=fsync)
if [[ "${CEDE_DD_NO_FSYNC:-0}" == "1" ]]; then
  _CONV=()
  echo "    (CEDE_DD_NO_FSYNC=1 — dd without fsync; will run sync after)" >&2
fi

echo "==> Writing $(basename "${IMAGE}") -> ${DEVICE}"
echo "    $(numfmt --to=iec-i --suffix=B "$(stat -c%s "${IMAGE}")" 2>/dev/null || stat -c%s "${IMAGE}") bytes"
echo "    Abort with Ctrl+C within ${DELAY_SEC}s if this is the wrong device..."
sleep "${DELAY_SEC}"

dd if="${IMAGE}" of="${DEVICE}" bs=4M status=progress "${_CONV[@]}"
sync
sync
echo "==> Done. Safely remove the device or run partprobe before re-reading partition tables."
