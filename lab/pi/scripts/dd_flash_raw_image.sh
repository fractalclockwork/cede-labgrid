#!/usr/bin/env bash
# Compatibility alias — see flash_raw_to_device.sh for Pi OS / generic raw flashing.

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${_SCRIPT_DIR}/flash_raw_to_device.sh" "$@"
