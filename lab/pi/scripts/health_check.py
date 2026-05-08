#!/usr/bin/env python3
"""Lightweight Pi gateway health: tools on PATH + optional lab serial resolution."""

from __future__ import annotations

import shutil
import subprocess
import sys

REQUIRED = ("picotool", "avrdude", "python3")


def _warn_if_pico_raw_uf2_may_fail() -> None:
    """cede-rp2 fallback copies UF2 to the RPI-RP2 block device when udisks mount is missing."""
    try:
        gnames = subprocess.run(
            ["id", "-nG"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    if "disk" in gnames:
        return
    sn = subprocess.run(["sudo", "-n", "true"], capture_output=True)
    if sn.returncode == 0:
        return
    print(
        "health: warning — not in group 'disk' and sudo -n is denied; "
        "cede-rp2 raw UF2 flash may fail without a mount. "
        "Fix: gateway bootstrap from Dev-Host or cloud-init (adds disk group)—see lab/pi/docs/sdcard.md—"
        "or re-image with current cloud-init (includes disk + NOPASSWD sudo).",
        file=sys.stderr,
    )


def main() -> int:
    missing = [b for b in REQUIRED if shutil.which(b) is None]
    if missing:
        print("missing:", ", ".join(missing), file=sys.stderr)
        return 1

    try:
        subprocess.run(["picotool", "version"], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print("picotool failed:", e, file=sys.stderr)
        return 1

    pyserial_ok = subprocess.run(
        ["python3", "-c", "import serial"], capture_output=True
    ).returncode == 0

    print("health: ok (picotool, avrdude, python3 present)")
    if not pyserial_ok:
        print(
            "health: warning — python3-serial missing; serial validators may fail. "
            "Install with: sudo apt-get install -y python3-serial",
            file=sys.stderr,
        )
    _warn_if_pico_raw_uf2_may_fail()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
