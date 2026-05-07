#!/usr/bin/env bash
# Shared helpers for flash_sdcard.sh and prepare_sdcard_boot.sh — source this file, do not execute.
# shellcheck shell=bash

_CEDE_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cede_repo_root_from_scripts() {
  cd "${_CEDE_SCRIPTS_DIR}/../../.." && pwd
}

cede_boot_partition() {
  local base="$1"
  if [[ "${base}" =~ mmcblk|nvme|loop ]]; then
    echo "${base}p1"
  else
    echo "${base}1"
  fi
}

cede_partprobe_sleep() {
  local dev="$1"
  echo "==> Re-reading partition table"
  partprobe "${dev}" 2>/dev/null || true
  sleep 2
}

# After rpi-imager or USB attach, partition nodes (e.g. /dev/sdc1) may appear late.
# Override attempts with CEDE_BOOT_PARTITION_WAIT_ATTEMPTS (default 45 seconds).
cede_wait_for_boot_partition() {
  local DEVICE="$1"
  local BOOT
  BOOT="$(cede_boot_partition "${DEVICE}")"
  local max_attempts="${CEDE_BOOT_PARTITION_WAIT_ATTEMPTS:-45}"
  local i
  for ((i = 1; i <= max_attempts; i++)); do
    if [[ -b "${BOOT}" ]]; then
      if [[ "${i}" -gt 1 ]]; then
        echo "==> Found boot partition ${BOOT}"
      fi
      return 0
    fi
    if [[ "${i}" -eq 1 ]]; then
      echo "==> Re-reading partition table (waiting for ${BOOT})"
    else
      echo "==> Still waiting for ${BOOT} (${i}/${max_attempts})..."
    fi
    partprobe "${DEVICE}" 2>/dev/null || true
    if command -v udevadm >/dev/null 2>&1; then
      udevadm settle --timeout=5 2>/dev/null || true
    fi
    sleep 1
  done
  return 1
}

# Optional: auth_keys_file (path to .pub), ssh_user (default pi — must match OS login user).
cede_render_cloud_init() {
  local repo="$1"
  local hostname="$2"
  local auth_keys_file="${3:-}"
  local ssh_user="${4:-pi}"
  (
    export OUT="${repo}/lab/pi/cloud-init/rendered"
    mkdir -p "${OUT}"
    export SSH_USER="${ssh_user}"
    export CEDE_TIMEZONE="${CEDE_TIMEZONE:-UTC}"
    export CEDE_LOCALE="${CEDE_LOCALE:-en_US.UTF-8}"
    if [[ -n "${auth_keys_file}" ]]; then
      export AUTHORIZED_KEYS_FILE="${auth_keys_file}"
    fi
    bash "${repo}/lab/pi/bootstrap/render_cloud_init.sh" "${hostname}"
  )
}

# Ensure mini-UART / GPIO serial console is usable on Pi 3+ (stable baud); idempotent.
cede_ensure_enable_uart() {
  local mnt="$1"
  local cfg="${mnt}/config.txt"
  [[ -f "${cfg}" ]] || return 0
  if grep -qE '^[[:space:]]*enable_uart[[:space:]]*=[[:space:]]*1' "${cfg}"; then
    return 0
  fi
  printf '\n# CEDE: serial console on GPIO14/15\nenable_uart=1\n' >> "${cfg}"
  echo "==> Appended enable_uart=1 to ${cfg}"
}

# Copy rendered cloud-init into a mounted FAT boot filesystem (path to mountpoint).
cede_cloud_init_copy_to_boot_mount() {
  local MNT="$1"
  local REPO_ROOT="$2"

  local UD MD NC
  UD="${REPO_ROOT}/lab/pi/cloud-init/rendered/user-data"
  MD="${REPO_ROOT}/lab/pi/cloud-init/rendered/meta-data"
  NC="${REPO_ROOT}/lab/pi/cloud-init/rendered/network-config"
  if [[ ! -f "${UD}" ]] || [[ ! -f "${MD}" ]] || [[ ! -f "${NC}" ]]; then
    echo "error: missing ${UD}, ${MD}, or ${NC}" >&2
    return 1
  fi

  cp -f "${UD}" "${MD}" "${NC}" "${MNT}/"
  # Raspberry Pi OS: zero-byte file "ssh" on the FAT boot partition enables sshd on early boots,
  # before cloud-init finishes (package_upgrade can defer SSH for many minutes otherwise).
  touch "${MNT}/ssh"
  cede_ensure_enable_uart "${MNT}"
}

# Mount FAT boot (caller ensures partition exists), copy rendered user-data + meta-data, flush, umount.
cede_cloud_init_copy_to_boot_partition() {
  local DEVICE="$1"
  local REPO_ROOT="$2"

  local BOOT
  BOOT="$(cede_boot_partition "${DEVICE}")"

  local MNT
  MNT="$(mktemp -d)"
  trap 'umount -lf "${MNT}" 2>/dev/null || true; rmdir "${MNT}" 2>/dev/null || true' EXIT

  echo "==> Mounting ${BOOT} and copying cloud-init"
  mount "${BOOT}" "${MNT}"
  cede_cloud_init_copy_to_boot_mount "${MNT}" "${REPO_ROOT}"
  if command -v blockdev >/dev/null 2>&1; then
    blockdev --flushbufs "${DEVICE}" 2>/dev/null || true
  fi
  umount "${MNT}"
  trap - EXIT
  rmdir "${MNT}"
  echo "==> cloud-init copied to boot partition"
}

# Render cloud-init, probe partitions, mount FAT boot, copy user-data + meta-data, flush, umount.
cede_cloud_init_install_to_sdcard() {
  local DEVICE="$1"
  local REPO_ROOT="$2"
  local HOSTNAME="$3"
  local AUTH_KEYS="${4:-}"
  local SSH_USER="${5:-pi}"

  echo "==> Rendering cloud-init for hostname ${HOSTNAME}"
  cede_render_cloud_init "${REPO_ROOT}" "${HOSTNAME}" "${AUTH_KEYS}" "${SSH_USER}"

  if ! cede_wait_for_boot_partition "${DEVICE}"; then
    local BOOT
    BOOT="$(cede_boot_partition "${DEVICE}")"
    echo "error: boot partition not found at ${BOOT}; replug USB reader and check lsblk ${DEVICE}" >&2
    return 1
  fi

  cede_cloud_init_copy_to_boot_partition "${DEVICE}" "${REPO_ROOT}"
}
