#!/usr/bin/env bash
# Loop-mount the boot partition (p1) of a Raspberry Pi OS .img read-only and verify
# cloud-init payload (user-data, meta-data, hostname).
#
# Usage:
#   sudo ./verify_boot_image.sh /path/to.img
#   sudo ./verify_boot_image.sh /path/to.img --compare-rendered
#
# Requires: util-linux (losetup, mount), cmp/diff (optional compare).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib_sdcard.sh
source "${SCRIPT_DIR}/lib_sdcard.sh"

COMPARE=0
IMG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compare-rendered)
      COMPARE=1
      shift
      ;;
    -*)
      echo "unknown option: $1" >&2
      exit 1
      ;;
    *)
      if [[ -n "${IMG}" ]]; then
        echo "error: unexpected argument: $1" >&2
        exit 1
      fi
      IMG="${1}"
      shift
      ;;
  esac
done

[[ -n "${IMG}" ]] || {
  echo "usage: sudo $0 [--compare-rendered] /path/to.img" >&2
  exit 1
}

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo $0 /path/to.img" >&2
  exit 1
fi

[[ -f "${IMG}" ]] || {
  echo "error: not a file: ${IMG}" >&2
  exit 1
}

REPO_ROOT="$(cede_repo_root_from_scripts)"
RENDER_UD="${REPO_ROOT}/lab/pi/cloud-init/rendered/user-data"
RENDER_MD="${REPO_ROOT}/lab/pi/cloud-init/rendered/meta-data"
RENDER_NC="${REPO_ROOT}/lab/pi/cloud-init/rendered/network-config"

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

echo "==> Loop-mount boot partition of ${IMG}"
LOOP="$(losetup -f --show -Pf "${IMG}")"
BOOT="${LOOP}p1"
[[ -b "${BOOT}" ]] || {
  echo "error: expected ${BOOT} (first partition not found)" >&2
  exit 1
}

mount -o ro "${BOOT}" "${MNT}"

echo "==> Boot partition contents (cloud-init / firmware highlights)"
ls -la "${MNT}" | head -40

for f in user-data meta-data network-config; do
  if [[ ! -f "${MNT}/${f}" ]]; then
    echo "error: missing ${f} on boot partition — Pi OS Trixie+ cloud-init expects all three alongside user-data/meta-data" >&2
    exit 1
  fi
  echo ""
  echo "----- ${f} (hostname excerpt) -----"
  if [[ "${f}" == "network-config" ]]; then
    grep -E '^network:|^  version:|renderer:|eth0:|wlan0:' "${MNT}/${f}" || true
  else
    grep -E '^hostname:|^#cloud-config|local-hostname' "${MNT}/${f}" || true
  fi
done

HN="$(grep -E '^hostname:' "${MNT}/user-data" | awk '{print $2}' | tr -d "'" || true)"
echo ""
echo "==> Parsed hostname from user-data: ${HN:-<missing>}"

if [[ ! -f "${MNT}/ssh" ]]; then
  echo ""
  echo "warn: empty bootfile \"ssh\" missing — Pi OS may not enable sshd until cloud-init completes"
fi

if [[ "${COMPARE}" -eq 1 ]]; then
  if [[ ! -f "${RENDER_UD}" ]] || [[ ! -f "${RENDER_MD}" ]] || [[ ! -f "${RENDER_NC}" ]]; then
    echo "error: missing rendered files; run: uv run python lab/pi/bootstrap/pi_bootstrap.py render" >&2
    exit 1
  fi
  echo ""
  echo "==> cmp vs lab/pi/cloud-init/rendered/"
  cmp "${MNT}/user-data" "${RENDER_UD}" && echo "user-data: identical." || {
    echo "user-data: DIFFER from rendered (image vs repo)" >&2
    diff -u "${RENDER_UD}" "${MNT}/user-data" | head -80 || true
    exit 1
  }
  cmp "${MNT}/meta-data" "${RENDER_MD}" && echo "meta-data: identical." || {
    echo "meta-data: DIFFER from rendered" >&2
    diff -u "${RENDER_MD}" "${MNT}/meta-data" | head -40 || true
    exit 1
  }
  cmp "${MNT}/network-config" "${RENDER_NC}" && echo "network-config: identical." || {
    echo "network-config: DIFFER from rendered" >&2
    diff -u "${RENDER_NC}" "${MNT}/network-config" | head -40 || true
    exit 1
  }
fi

echo ""
echo "OK: boot partition contains cloud-init payload."
