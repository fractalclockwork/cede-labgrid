#!/usr/bin/env bash
# Run Pi gateway checks and MCU flashing from the dev-host (SSH into cede-pi, optional rsync/scp).
#
# Environment:
#   GATEWAY               — SSH target (default: pi@cede-pi.local)
#   GATEWAY_REPO_ROOT      — Sparse flash-deps root ON the Pi (default: ~/cede); NOT a full git checkout
#   UNO_ONLY              — when syncing deps, omit Pico helpers (same as sync_gateway_flash_deps.sh)
#
# Usage (from repo root unless noted):
#   GATEWAY=pi@cede-pi.local lab/pi/scripts/devhost_pi_gateway.sh health
#   lab/pi/scripts/devhost_pi_gateway.sh resolve-port-uno | resolve-port-pico
#   lab/pi/scripts/devhost_pi_gateway.sh flash-uno --hex … [--port …]
#   lab/pi/scripts/devhost_pi_gateway.sh flash-pico --uf2 … [--bootsel-only] [--no-sync]
#   PICO_WAIT_MOUNT — optional seconds for RPI-RP2 mount poll (passed to Pi make flash-pico-auto)
#   lab/pi/scripts/devhost_pi_gateway.sh validate-uno-serial | validate-pico-serial [--port …]

set -euo pipefail

usage() {
  sed -n '1,14p' "$0"
  exit "${1:-0}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_LOCAL="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

GATEWAY="${GATEWAY:-pi@cede-pi.local}"
# Do not use ${VAR:-~/cede}: ~ expands to the dev-host home. Keep a literal ~/… for the gateway.
if [[ -z "${GATEWAY_REPO_ROOT:-}" ]]; then
  GATEWAY_REPO_ROOT='~/cede'
fi

sync_deps() {
  UNO_ONLY="${UNO_ONLY:-}" bash "${SCRIPT_DIR}/sync_gateway_flash_deps.sh" "${GATEWAY}" "${GATEWAY_REPO_ROOT}"
}

# Full Pico helper sync (clears UNO_ONLY=1 for this rsync).
sync_pico_deps() {
  UNO_ONLY= bash "${SCRIPT_DIR}/sync_gateway_flash_deps.sh" "${GATEWAY}" "${GATEWAY_REPO_ROOT}"
}

# Run argv (after GATEWAY_REPO_ROOT) on the gateway under GATEWAY_REPO_ROOT.
_remote_repo() {
  ssh "${GATEWAY}" bash -s -- "${GATEWAY_REPO_ROOT}" "$@" <<'REMOTE'
set -euo pipefail
_root="${1}"
shift
case "${_root}" in
  "~")
    cd "${HOME}"
    ;;
  ~/*)
    cd "${HOME}/${_root#~/}"
    ;;
  *)
    cd "${_root}"
    ;;
esac
exec "$@"
REMOTE
}

remote() {
  _remote_repo "$@"
}

# Print one line (Uno tty path) from resolver on the gateway; stderr forwarded.
gateway_pick_uno_port() {
  _remote_repo python3 lab/pi/scripts/pi_resolve_gateway_uno.py
}

gateway_pick_pico_port() {
  _remote_repo python3 lab/pi/scripts/pi_resolve_gateway_pico.py
}

cmd_resolve_port_uno() {
  gateway_pick_uno_port
}

cmd_resolve_port_pico() {
  gateway_pick_pico_port
}

cmd_health() {
  remote python3 lab/pi/scripts/health_check.py
}

cmd_subtarget_check() {
  remote make -C lab/pi subtarget-check
}

cmd_print_serial() {
  remote make -C lab/pi print-serial
}

cmd_validate_uno_serial() {
  local port=""
  local extra_args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="${2:?}"; shift 2 ;;
      --expect) extra_args+=(--expect "${2:?}"); shift 2 ;;
      --wait) extra_args+=(--wait "${2:?}"); shift 2 ;;
      -h|--help) usage 0 ;;
      *) echo "unknown arg: $1" >&2; usage 1 ;;
    esac
  done

  if [[ -z "${port}" ]]; then
    if [[ "${SKIP_SYNC:-}" != "1" ]]; then
      sync_deps
    fi
    echo "==> gateway: resolve Uno serial port …" >&2
    port="$(gateway_pick_uno_port)"
    echo "==> using PORT=${port}" >&2
  fi
  remote python3 lab/pi/scripts/pi_validate_uno_serial.py "${extra_args[@]}" "${port}"
}

cmd_flash_uno() {
  local hex="" port="" do_sync=1
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --hex) hex="${2:?}"; shift 2 ;;
      --port) port="${2:?}"; shift 2 ;;
      --no-sync) do_sync=0; shift ;;
      -h|--help) usage 0 ;;
      *) echo "unknown arg: $1" >&2; usage 1 ;;
    esac
  done

  [[ -n "${hex}" ]] || {
    echo "error: --hex required" >&2
    usage 1
  }

  hex="$(cd "${REPO_LOCAL}" && realpath "${hex}")"
  [[ -f "${hex}" ]] || {
    echo "error: HEX file not found: ${hex}" >&2
    exit 1
  }

  local base
  base="$(basename "${hex}")"

  if [[ "${do_sync}" -eq 1 ]]; then
    sync_deps
  fi

  if [[ -z "${port}" ]]; then
    echo "==> gateway: resolve Uno serial port …" >&2
    port="$(gateway_pick_uno_port)"
    echo "==> using PORT=${port}" >&2
  fi

  echo "==> scp ${hex} -> ${GATEWAY}:/tmp/${base}"
  scp "${hex}" "${GATEWAY}:/tmp/${base}"

  echo "==> ssh ${GATEWAY} flash-uno (PORT=${port})"
  remote make -C lab/pi flash-uno HEX="/tmp/${base}" PORT="${port}"
}

cmd_validate_pico_serial() {
  local port=""
  local extra_args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="${2:?}"; shift 2 ;;
      --expect) extra_args+=(--expect "${2:?}"); shift 2 ;;
      --wait) extra_args+=(--wait "${2:?}"); shift 2 ;;
      -h|--help) usage 0 ;;
      *) echo "unknown arg: $1" >&2; usage 1 ;;
    esac
  done

  if [[ -z "${port}" ]]; then
    if [[ "${SKIP_SYNC:-}" != "1" ]]; then
      sync_pico_deps
    fi
    echo "==> gateway: resolve cede-rp2 (Pico) serial port …" >&2
    port="$(_remote_repo python3 lab/pi/scripts/pi_resolve_gateway_pico.py --wait "${PICO_VALIDATE_WAIT:-3}")"
    echo "==> using PORT=${port}" >&2
  fi
  local _has_wait=0
  for _x in "${extra_args[@]}"; do
    if [[ "${_x}" == --wait ]]; then
      _has_wait=1
      break
    fi
  done
  if [[ "${_has_wait}" -eq 0 ]]; then
    extra_args+=(--wait "${PICO_VALIDATE_WAIT:-3}")
  fi
  unset _x _has_wait
  remote python3 lab/pi/scripts/pi_validate_pico_serial.py "${extra_args[@]}" "${port}"
}

cmd_flash_pico() {
  local uf2="" do_sync=1 bootsel_only=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --uf2) uf2="${2:?}"; shift 2 ;;
      --bootsel-only) bootsel_only=1; shift ;;
      --no-sync) do_sync=0; shift ;;
      -h|--help) usage 0 ;;
      *) echo "unknown arg: $1" >&2; usage 1 ;;
    esac
  done

  [[ -n "${uf2}" ]] || {
    echo "error: --uf2 required" >&2
    usage 1
  }

  uf2="$(cd "${REPO_LOCAL}" && realpath "${uf2}")"
  [[ -f "${uf2}" ]] || {
    echo "error: UF2 file not found: ${uf2}" >&2
    exit 1
  }

  local base
  base="$(basename "${uf2}")"

  if [[ "${do_sync}" -eq 1 ]]; then
    sync_pico_deps
  fi

  echo "==> scp ${uf2} -> ${GATEWAY}:/tmp/${base}"
  scp "${uf2}" "${GATEWAY}:/tmp/${base}"

  echo "==> ssh ${GATEWAY} flash-pico-auto (cede-rp2)"
  local -a _mk
  if [[ "${bootsel_only}" -eq 1 ]]; then
    _mk=(make -C lab/pi UF2="/tmp/${base}" PICO_BOOTSEL_ONLY=1 flash-pico-auto)
  else
    _mk=(make -C lab/pi UF2="/tmp/${base}" flash-pico-auto)
  fi
  if [[ -n "${PICO_WAIT_MOUNT:-}" ]]; then
    _mk=(env PICO_WAIT_MOUNT="${PICO_WAIT_MOUNT}" "${_mk[@]}")
  fi
  if ! remote "${_mk[@]}"; then
    exit 1
  fi
}

case "${1:-}" in
  "")
    usage 1
    ;;
  -h|--help)
    usage 0
    ;;
  health)
    cmd_health
    ;;
  resolve-port-uno)
    cmd_resolve_port_uno
    ;;
  resolve-port-pico)
    cmd_resolve_port_pico
    ;;
  subtarget-check)
    cmd_subtarget_check
    ;;
  print-serial)
    cmd_print_serial
    ;;
  sync)
    sync_deps
    ;;
  flash-uno)
    shift
    cmd_flash_uno "$@"
    ;;
  validate-uno-serial)
    shift
    cmd_validate_uno_serial "$@"
    ;;
  validate-pico-serial)
    shift
    cmd_validate_pico_serial "$@"
    ;;
  flash-pico)
    shift
    cmd_flash_pico "$@"
    ;;
  *)
    echo "unknown command: $1" >&2
    usage 1
    ;;
esac
