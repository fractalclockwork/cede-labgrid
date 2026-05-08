# -*- shell-script -*-
# Shared RPI-RP2 (Pico BOOTSEL) discovery for pi_flash_pico_*.sh — source from same directory only.
# Resolves the FAT partition by label via udev symlink, blkid(8), or lsblk(8); optional raw UF2 copy.
# Non-login SSH/make often omit /sbin from PATH; blkid lives in /sbin on Raspberry Pi OS.

_cede_blkid_bin() {
  if command -v blkid >/dev/null 2>&1; then
    echo "blkid"
  elif [[ -x /sbin/blkid ]]; then
    echo "/sbin/blkid"
  fi
}

resolve_rpi_rp2_partition() {
  local dev p path lab name _bb
  dev="/dev/disk/by-label/RPI-RP2"
  if [[ -e "$dev" ]]; then
    readlink -f "$dev" 2>/dev/null || echo "$dev"
    return 0
  fi
  _bb="$(_cede_blkid_bin)"
  if [[ -n "${_bb}" ]]; then
    p="$("${_bb}" -L 'RPI-RP2' 2>/dev/null || true)"
    if [[ -n "$p" ]] && [[ -b "$p" ]]; then
      echo "$p"
      return 0
    fi
  fi
  if command -v lsblk >/dev/null 2>&1; then
    while read -r path lab; do
      [[ "$lab" == "RPI-RP2" ]] || continue
      [[ -n "$path" ]] && [[ -b "$path" ]] && echo "$path" && return 0
    done < <(lsblk -nrpo PATH,LABEL 2>/dev/null || true)
    while read -r name lab; do
      [[ "$lab" == "RPI-RP2" ]] || continue
      [[ -z "$name" ]] && continue
      if [[ "$name" == /dev/* ]] && [[ -b "$name" ]]; then
        echo "$name"
        return 0
      fi
      if [[ -b "/dev/${name}" ]]; then
        echo "/dev/${name}"
        return 0
      fi
    done < <(lsblk -nrpo NAME,LABEL 2>/dev/null || true)
  fi
  return 1
}

partition_is_rpi_rp2_label() {
  local part="${1:-}" lab="" _bb
  [[ -n "$part" ]] && [[ -b "$part" ]] || return 1
  _bb="$(_cede_blkid_bin)"
  if [[ -n "${_bb}" ]]; then
    lab="$("${_bb}" -o value -s LABEL "$part" 2>/dev/null || true)"
    lab="${lab//$'\n'/}"
  fi
  if [[ "$lab" != "RPI-RP2" ]] && command -v lsblk >/dev/null 2>&1; then
    lab="$(lsblk -no LABEL "$part" 2>/dev/null | head -n1 || true)"
    lab="${lab//$'\n'/}"
  fi
  [[ "$lab" == "RPI-RP2" ]]
}

find_rpi_rp2_mount() {
  local d t part resolved
  for d in /media/*/"RPI-RP2" /run/media/*/"RPI-RP2"; do
    if [[ -d "$d" ]]; then
      if command -v mountpoint >/dev/null 2>&1; then
        mountpoint -q "$d" 2>/dev/null || continue
      fi
      echo "$d"
      return 0
    fi
  done

  part=""
  part="$(resolve_rpi_rp2_partition)" || true
  [[ -z "$part" ]] && return 1
  resolved="$part"

  if command -v findmnt >/dev/null 2>&1; then
    t="$(findmnt -n -o TARGET "$resolved" 2>/dev/null || true)"
  fi
  if [[ -n "${t:-}" ]] && [[ -d "$t" ]]; then
    echo "$t"
    return 0
  fi

  if command -v udisksctl >/dev/null 2>&1; then
    udisksctl mount -b "$resolved" >/dev/null 2>&1 || true
    sleep 0.35
    if command -v findmnt >/dev/null 2>&1; then
      t="$(findmnt -n -o TARGET "$resolved" 2>/dev/null || true)"
    fi
    if [[ -n "${t:-}" ]] && [[ -d "$t" ]]; then
      echo "$t"
      return 0
    fi
  fi

  return 1
}

# Copy UF2 to a block device as normal user, or with sudo -n when gateway uses NOPASSWD (see cloud-init).
_copy_uf2_to_raw_block() {
  local uf2="${1:?}" part="${2:?}"
  if cp -v "$uf2" "$part" 2>/dev/null; then
    sync
    return 0
  fi
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    echo "==> raw copy needs privileges; using sudo -n cp …" >&2
    if sudo -n cp -v "$uf2" "$part"; then
      sync
      return 0
    fi
  fi
  return 1
}

# When no mount point appears (no udisks / no automount), copy UF2 to the verified RPI-RP2 partition device.
try_fallback_uf2_to_rpi_rp2_partition() {
  local uf2="${1:?}" wait_sec="${2:-35}"
  local deadline=$((SECONDS + wait_sec)) part mp
  while (( SECONDS < deadline )); do
    part="$(resolve_rpi_rp2_partition)" || true
    if [[ -n "$part" ]] && partition_is_rpi_rp2_label "$part"; then
      mp=""
      if command -v findmnt >/dev/null 2>&1; then
        mp="$(findmnt -n -o TARGET "$part" 2>/dev/null || true)"
      fi
      if [[ -n "$mp" ]] && [[ -d "$mp" ]]; then
        echo "==> Copy $(basename "$uf2") -> ${mp}"
        cp -v "$uf2" "${mp}/"
        sync
        return 0
      fi
      echo "==> Copy $(basename "$uf2") -> ${part} (raw block device; no mount point)"
      if _copy_uf2_to_raw_block "$uf2" "$part"; then
        return 0
      fi
      echo "error: could not write UF2 to ${part}. Add user to group disk (gateway bootstrap / cloud-init) or ensure sudo -n works for this user." >&2
      return 1
    fi
    sleep 0.4
  done
  return 1
}
