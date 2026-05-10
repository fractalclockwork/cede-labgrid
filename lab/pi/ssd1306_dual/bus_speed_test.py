#!/usr/bin/env python3
"""Dual SSD1306 I2C throughput benchmark (full-frame draws on both panels).

Measures how many complete round-trips per second the Pi can push through **both** displays on the
same bus (each round = full refresh of display A then display B). Uses the same drawing path as
``main.py`` (``canvas`` → packed framebuffer → I2C).

For higher line rates, raise the Pi I2C clock (e.g. ``dtparam=i2c_arm_baudrate=400000`` in
``/boot/firmware/config.txt``) after wiring allows it — see README.

Requires: ``pip install -r requirements.txt`` (on the Pi).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bus", type=int, default=1, help="Linux I2C bus (default 1)")
    p.add_argument(
        "--addr-a",
        type=lambda x: int(x, 0),
        default=0x3C,
        metavar="ADDR",
        help="7-bit address display A (default 0x3C)",
    )
    p.add_argument(
        "--addr-b",
        type=lambda x: int(x, 0),
        default=0x3D,
        metavar="ADDR",
        help="7-bit address display B (default 0x3D)",
    )
    p.add_argument("--rotate", type=int, default=0, choices=(0, 1, 2, 3), help="Rotation steps")
    p.add_argument(
        "--duration",
        type=float,
        default=10.0,
        metavar="SEC",
        help="Timed measurement window in seconds (default 10)",
    )
    p.add_argument(
        "--warmup",
        type=float,
        default=0.35,
        metavar="SEC",
        help="Warmup full-frame cycles before timing (default 0.35)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print one JSON object with metrics (no banner text)",
    )
    return p.parse_args()


def open_display(bus: int, addr: int, rotate: int) -> ssd1306:
    serial = i2c(port=bus, address=addr)
    return ssd1306(serial, rotate=rotate)


def packed_framebuffer_bytes(dev: ssd1306) -> int:
    """1 bpp packed buffer typical for SSD1306 horizontal addressing."""
    return (dev.width * dev.height) // 8


def run_benchmark(
    devices: tuple[ssd1306, ...],
    *,
    duration: float,
    warmup: float,
) -> tuple[int, float]:
    """Returns (round_count, elapsed_seconds) where one round updates every device once."""

    phase = 0
    if warmup > 0:
        w_end = time.monotonic() + warmup
        while time.monotonic() < w_end:
            fill = "white" if phase & 1 else "black"
            for dev in devices:
                with canvas(dev) as draw:
                    draw.rectangle(dev.bounding_box, outline=fill, fill=fill)
            phase += 1

    count = 0
    t0 = time.monotonic()
    deadline = t0 + duration
    while time.monotonic() < deadline:
        fill = "white" if count & 1 else "black"
        for dev in devices:
            with canvas(dev) as draw:
                draw.rectangle(dev.bounding_box, outline=fill, fill=fill)
        count += 1
    t1 = time.monotonic()
    elapsed = max(t1 - t0, 1e-9)
    return count, elapsed


def main() -> int:
    args = parse_args()
    if args.addr_a == args.addr_b:
        print("error: --addr-a and --addr-b must differ", file=sys.stderr)
        return 2
    if args.duration <= 0:
        print("error: --duration must be positive", file=sys.stderr)
        return 2

    try:
        devices = (
            open_display(args.bus, args.addr_a, args.rotate),
            open_display(args.bus, args.addr_b, args.rotate),
        )
    except OSError as e:
        print(
            f"error: could not open I2C displays (i2cdetect -y {args.bus}): {e}",
            file=sys.stderr,
        )
        return 1

    rounds, elapsed = run_benchmark(devices, duration=args.duration, warmup=args.warmup)

    bpp_total = sum(packed_framebuffer_bytes(d) for d in devices)
    dual_rounds_per_s = rounds / elapsed
    panel_updates_per_s = (rounds * len(devices)) / elapsed
    approx_kib_s = (rounds * bpp_total) / elapsed / 1024.0

    try:
        for dev in devices:
            dev.hide()
    except OSError:
        pass

    payload = {
        "bus": args.bus,
        "addr_a": args.addr_a,
        "addr_b": args.addr_b,
        "duration_s": elapsed,
        "warmup_s": args.warmup,
        "dual_rounds": rounds,
        "dual_rounds_per_s": round(dual_rounds_per_s, 2),
        "panel_full_frames_per_s": round(panel_updates_per_s, 2),
        "approx_framebuffer_kib_s": round(approx_kib_s, 2),
        "approx_bytes_per_dual_round": bpp_total,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print("CEDE dual SSD1306 bus speed test")
    print(f"  bus={args.bus}  addr_a=0x{args.addr_a:02x}  addr_b=0x{args.addr_b:02x}")
    print(f"  timed window: {elapsed:.3f}s (requested {args.duration}s)")
    print(f"  dual rounds (both panels refreshed once each): {rounds}")
    print(f"  dual rounds/s:              {dual_rounds_per_s:,.2f}")
    print(f"  panel full-frame draws/s:   {panel_updates_per_s:,.2f}  (2 × dual rounds/s)")
    print(
        f"  approx framebuffer KiB/s:   {approx_kib_s:,.2f}  "
        f"(~{bpp_total} B full buffers per dual round)"
    )
    print()
    print("Tip: increase Pi I2C clock if wiring allows (e.g. i2c_arm_baudrate=400000).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
