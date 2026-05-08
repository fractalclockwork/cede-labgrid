#!/usr/bin/env python3
"""Pick USB serial path for cede-rp2 (Raspberry Pi Pico / RP2040) on the gateway.

Prefer /dev/serial/by-id/usb-Raspberry_Pi_*; else lone /dev/ttyACM* not claimed by usb-Arduino_*.
Stdout: one tty path suitable for CDC and validation tools."""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time


def _explain(msg: str) -> None:
    print(msg, file=sys.stderr)


def _arduino_tty_realpaths() -> set[str]:
    out: set[str] = set()
    for p in glob.glob("/dev/serial/by-id/usb-Arduino*"):
        try:
            if os.path.exists(p):
                out.add(os.path.realpath(p))
        except OSError:
            continue
    return out


def _uniq_sorted(pattern: str) -> list[str]:
    return sorted(set(glob.glob(pattern)))


def resolve_pico_tty() -> str | None:
    pico_links = _uniq_sorted("/dev/serial/by-id/usb-Raspberry_Pi*")
    if len(pico_links) == 1:
        return pico_links[0]
    if len(pico_links) > 1:
        _explain("ambiguous: multiple Raspberry Pi Pico by-id paths ( unplug extras or specify PORT ):")
        for p in pico_links:
            _explain(f"  {p} -> {os.path.realpath(p)}")
        return None

    arduino = _arduino_tty_realpaths()
    acms = [p for p in _uniq_sorted("/dev/ttyACM*") if os.path.realpath(p) not in arduino]

    if len(acms) == 1:
        return acms[0]
    if len(acms) > 1:
        _explain("ambiguous: multiple non-Arduino ACM devices ( specify PORT ); candidates:")
        for p in acms:
            _explain(f"  {p} -> {os.path.realpath(p)}")
        return None

    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--check",
        action="store_true",
        help="exit 0 if exactly one path resolves, else non-zero",
    )
    p.add_argument(
        "--wait",
        type=float,
        default=0.0,
        metavar="SEC",
        help="poll up to SEC seconds for a unique tty (after UF2 flash / USB re-enumeration)",
    )
    args = p.parse_args()

    deadline = time.monotonic() + max(0.0, args.wait)
    path: str | None = None
    while True:
        path = resolve_pico_tty()
        if path is not None:
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.35)

    if path is None:
        pico = _uniq_sorted("/dev/serial/by-id/usb-Raspberry_Pi*")
        acm_all = _uniq_sorted("/dev/ttyACM*")
        arduino = _arduino_tty_realpaths()
        acms_free = [p for p in acm_all if os.path.realpath(p) not in arduino]
        if len(pico) > 1:
            _explain("hint: multiple usb-Raspberry_Pi* by-id paths; unplug extras or set PORT=")
        elif len(acms_free) > 1:
            _explain("hint: multiple non-Arduino ttyACM devices; set PORT=")
        elif pico or acm_all:
            _explain(
                "hint: no unique cede-rp2 tty (Pico unplugged, still booting, or only non-Pico ACM). "
                "Try: ls -l /dev/serial/by-id/ ; python3 …/pi_resolve_gateway_pico.py --wait 15 ; "
                "run scripts from the same tree you synced (e.g. ~/src/cede/lab/… not ~/cede/lab/…); "
                "or set PORT=/dev/ttyACM…"
            )
        else:
            _explain("no Pico-like serial device found (plug board / check USB)")
        return 2

    if args.check:
        return 0
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
