#!/usr/bin/env python3
"""Pick /dev serial path for an Arduino-class Uno on the gateway (ordering / plug order–safe).

Prefer stable /dev/serial/by-id/usb-Arduino_* links, then CH340 ttyUSB*, then ACM that is not a Pico symlink.
Stdout: one tty path suitable for avrdude and serial tools."""

from __future__ import annotations

import argparse
import glob
import os
import sys


def _explain(msg: str) -> None:
    print(msg, file=sys.stderr)


def _pico_tty_realpaths() -> set[str]:
    out = set()
    for p in glob.glob("/dev/serial/by-id/usb-Raspberry_Pi*"):
        try:
            if os.path.exists(p):
                out.add(os.path.realpath(p))
        except OSError:
            continue
    return out


def _uniq_sorted(pattern: str) -> list[str]:
    return sorted(set(glob.glob(pattern)))


def resolve_uno_tty() -> str | None:
    arduino_links = _uniq_sorted("/dev/serial/by-id/usb-Arduino*")
    if len(arduino_links) == 1:
        return arduino_links[0]
    if len(arduino_links) > 1:
        _explain("ambiguous: multiple Arduino by-id paths ( unplug extras or specify PORT ):")
        for p in arduino_links:
            _explain(f"  {p} -> {os.path.realpath(p)}")
        return None

    ttyusb = _uniq_sorted("/dev/ttyUSB*")
    if len(ttyusb) == 1:
        return ttyusb[0]
    if len(ttyusb) > 1:
        _explain("ambiguous: multiple /dev/ttyUSB* devices; specify PORT or use Arduino by-id")
        for p in ttyusb:
            _explain(f"  {p}")
        return None

    pico = _pico_tty_realpaths()
    acms = [p for p in _uniq_sorted("/dev/ttyACM*") if os.path.realpath(p) not in pico]

    if len(acms) == 1:
        return acms[0]
    if len(acms) > 1:
        _explain("ambiguous: multiple non-Pico ACM devices ( specify PORT ); candidates:")
        for p in acms:
            rp = os.path.realpath(p)
            _explain(f"  {p} -> {rp}")
        _explain("(also list /dev/serial/by-id/ if clones lack stable ids)")
        return None

    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--check",
        action="store_true",
        help="exit 0 if exactly one resolved path exists, otherwise non-zero without printing noise",
    )
    args = p.parse_args()

    path = resolve_uno_tty()
    if path is None:
        if glob.glob("/dev/ttyACM*") or glob.glob("/dev/ttyUSB*"):
            _explain(
                "hint: Uno/Pico/conflict resolution failed; try `ls -l /dev/serial/by-id/` on the gateway"
            )
        else:
            _explain("no Uno-like serial device found (plug board / check USB)")
        return 2 if args.check else 2

    if args.check:
        return 0
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
