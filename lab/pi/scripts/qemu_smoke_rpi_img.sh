#!/usr/bin/env bash
# Serial-only QEMU smoke boot of a Raspberry Pi OS raw .img (kernel + dtb read from bootfs).
# Requires sudo for loop-mount during extraction. Not hardware-accurate — see lab/pi/emulate/README.md
#
# Usage:
#   sudo ./qemu_smoke_rpi_img.sh /path/to.img
#
# Env:
#   CEDE_QEMU_TIMEOUT_SEC       default 120
#   CEDE_QEMU_SERIAL_LOG        default /tmp/cede-qemu-serial.log
#   CEDE_QEMU_SUCCESS_PATTERN   grep -E on serial log; default looks for Linux or cloud-init

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo $0 /path/to.img" >&2
  exit 1
fi

IMG="${1:?usage: sudo $0 /path/to.img}"

if ! command -v qemu-system-aarch64 >/dev/null 2>&1; then
  echo "error: qemu-system-aarch64 not installed (e.g. apt install qemu-system-arm)" >&2
  exit 2
fi

TIMEOUT="${CEDE_QEMU_TIMEOUT_SEC:-120}"
SER_LOG="${CEDE_QEMU_SERIAL_LOG:-/tmp/cede-qemu-serial.log}"
SUCCESS_RE="${CEDE_QEMU_SUCCESS_PATTERN:-Linux version|cloud-init|Reached target}"

WORKDIR="$(mktemp -d)"
MNT="$(mktemp -d)"
LOOP=""

cleanup() {
  umount -lf "${MNT}" 2>/dev/null || true
  if [[ -n "${LOOP}" ]] && losetup "${LOOP}" >/dev/null 2>&1; then
    losetup -d "${LOOP}" 2>/dev/null || true
  fi
  rm -rf "${WORKDIR}"
  rmdir "${MNT}" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Extract kernel / dtb from boot partition"
LOOP="$(losetup -f --show -Pf "${IMG}")"
mount -o ro "${LOOP}p1" "${MNT}"

K="${MNT}/kernel8.img"
[[ -f "${K}" ]] || K="$(find "${MNT}" -maxdepth 1 -name 'kernel*.img' -type f | sort | head -1)"
[[ -n "${K}" && -f "${K}" ]] || {
  echo "error: no kernel image on boot partition" >&2
  exit 1
}

DTB="${MNT}/bcm2710-rpi-3-b-plus.dtb"
[[ -f "${DTB}" ]] || DTB="$(find "${MNT}" -maxdepth 1 -name 'bcm2710-rpi-*.dtb' -type f | sort | head -1)"
[[ -f "${DTB}" ]] || DTB="$(find "${MNT}" -maxdepth 1 -name 'bcm2711-rpi-*.dtb' -type f | sort | head -1)"
[[ -n "${DTB}" && -f "${DTB}" ]] || {
  echo "error: no bcm271*.dtb on boot partition" >&2
  exit 1
}

cp -f "${K}" "${WORKDIR}/kernel.img"
cp -f "${DTB}" "${WORKDIR}/firmware.dtb"
APPEND="console=ttyAMA0,115200 root=/dev/mmcblk0p2 rootfstype=ext4 rootwait rw"
if [[ -f "${MNT}/cmdline.txt" ]]; then
  APPEND="$(tr '\n' ' ' <"${MNT}/cmdline.txt") ${APPEND}"
fi

umount "${MNT}"
losetup -d "${LOOP}"
LOOP=""

echo "==> QEMU (-M raspi3b) serial → ${SER_LOG} (timeout ${TIMEOUT}s)"
rm -f "${SER_LOG}"

set +e
timeout "${TIMEOUT}" qemu-system-aarch64 \
  -M raspi3b \
  -m 1024 \
  -kernel "${WORKDIR}/kernel.img" \
  -dtb "${WORKDIR}/firmware.dtb" \
  -drive "file=${IMG},format=raw,if=sd,index=0" \
  -append "${APPEND}" \
  -serial "file:${SER_LOG}" \
  -display none \
  -no-reboot </dev/null
RC=$?
set -e

echo "==> qemu exit ${RC} (124 = timeout — kernel may still have booted)"
if [[ -f "${SER_LOG}" ]]; then
  echo "----- last 35 lines -----"
  tail -35 "${SER_LOG}"
  echo "----- pattern (${SUCCESS_RE}) -----"
  if grep -aE "${SUCCESS_RE}" "${SER_LOG}" >/dev/null 2>&1; then
    echo "OK: serial log matched pattern."
    exit 0
  fi
fi
echo "warn: pattern not matched — inspect ${SER_LOG}; QEMU/Pi OS/kernel pairing varies by release."
exit 1
