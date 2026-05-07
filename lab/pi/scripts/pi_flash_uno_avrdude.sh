#!/usr/bin/env bash
# Flash Arduino Uno (ATmega328P + bootloader) via avrdude. Run ON the Raspberry Pi gateway.
#
# Usage:
#   ./pi_flash_uno_avrdude.sh --hex /path/hello.ino.hex --port /dev/ttyACM0 --yes

set -euo pipefail

usage() {
  sed -n '1,8p' "$0"
  exit "${1:-0}"
}

HEX=""
PORT=""
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hex)
      HEX="${2:?}"
      shift 2
      ;;
    --port)
      PORT="${2:?}"
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
  echo "refusing: pass --yes after confirming PORT is the Uno, not Pico" >&2
  exit 1
fi

if [[ -z "${HEX}" ]] || [[ ! -f "${HEX}" ]]; then
  echo "error: --hex must name an existing file" >&2
  exit 1
fi

if [[ -z "${PORT}" ]]; then
  echo "error: --port required (e.g. /dev/ttyACM1)" >&2
  exit 1
fi

if [[ ! -c "${PORT}" ]] && [[ ! -e "${PORT}" ]]; then
  echo "warn: ${PORT} missing; avrdude may still work if device appears shortly" >&2
fi

echo "==> avrdude -> ${PORT} ($(basename "${HEX}"))"
avrdude -p atmega328p -c arduino -P "${PORT}" -b 115200 -D -U "flash:w:${HEX}:i"
echo "==> Done."
