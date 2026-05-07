#!/usr/bin/env bash
# Render cloud-init templates for a given hostname. Writes lab/pi/cloud-init/rendered/.
#
# Usage:
#   ./render_cloud_init.sh <hostname>
#   AUTHORIZED_KEYS_FILE=/path/to/id_ed25519.pub ./render_cloud_init.sh <hostname>
#   SSH_USER=pi AUTHORIZED_KEYS_FILE=... ./render_cloud_init.sh <hostname>
#   CEDE_TIMEZONE=UTC CEDE_LOCALE=en_US.UTF-8 ./render_cloud_init.sh <hostname>
#
# Optional Wi-Fi (also via pi_bootstrap.py from lab.yaml):
#   CEDE_WIFI_SSID=... CEDE_WIFI_PSK=... ./render_cloud_init.sh <hostname>
#
# Implementation: lab/pi/bootstrap/cloud_init_render.py (requires python3-yaml).
set -euo pipefail

HOSTNAME="${1:-}"
if [[ -z "${HOSTNAME}" ]]; then
  echo "usage: $0 <hostname>" >&2
  echo "  optional env: AUTHORIZED_KEYS_FILE, SSH_USER (default: pi)" >&2
  echo "  optional env: CEDE_TIMEZONE, CEDE_LOCALE, CEDE_WIFI_SSID, CEDE_WIFI_PSK" >&2
  echo "  example: AUTHORIZED_KEYS_FILE=~/.ssh/id_ed25519.pub $0 cede-gateway" >&2
  exit 1
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../.." && pwd)"

SSH_USER="${SSH_USER:-pi}"
PY_ARGS=(--repo "${REPO_ROOT}" "${HOSTNAME}" --ssh-user "${SSH_USER}" --timezone "${CEDE_TIMEZONE:-UTC}" --locale "${CEDE_LOCALE:-en_US.UTF-8}")

if [[ -n "${AUTHORIZED_KEYS_FILE:-}" ]]; then
  PY_ARGS+=(--authorized-keys "${AUTHORIZED_KEYS_FILE}")
fi
if [[ -n "${CEDE_WIFI_SSID:-}" ]]; then
  PY_ARGS+=(--wifi-ssid "${CEDE_WIFI_SSID}")
  if [[ -n "${CEDE_WIFI_PSK_FILE:-}" ]]; then
    PY_ARGS+=(--wifi-psk-file "${CEDE_WIFI_PSK_FILE}")
  elif [[ -n "${CEDE_WIFI_PSK:-}" ]]; then
    PY_ARGS+=(--wifi-psk "${CEDE_WIFI_PSK}")
  fi
fi

exec python3 "${HERE}/cloud_init_render.py" "${PY_ARGS[@]}"
