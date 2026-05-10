#!/usr/bin/env python3
"""Drive two SSD1306 OLED panels over Linux I2C (128x64 typical).

Requires: pip install -r requirements.txt (on the Pi). Default addresses 0x3C and 0x3D — set
jumpers so both displays differ on the same bus (see README.md).
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Sequence

from PIL import ImageFont
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--bus",
        type=int,
        default=1,
        help="Linux I2C bus number (default 1 = Pi GPIO2/3)",
    )
    p.add_argument(
        "--addr-a",
        type=lambda x: int(x, 0),
        default=0x3C,
        metavar="ADDR",
        help="7-bit I2C address for display A (default 0x3C)",
    )
    p.add_argument(
        "--addr-b",
        type=lambda x: int(x, 0),
        default=0x3D,
        metavar="ADDR",
        help="7-bit I2C address for display B (default 0x3D)",
    )
    p.add_argument(
        "--rotate",
        type=int,
        default=0,
        choices=(0, 1, 2, 3),
        help="Framebuffer rotation steps (0–3)",
    )
    p.add_argument(
        "--fps",
        type=float,
        default=8.0,
        help="Redraw rate for the bounce demo",
    )
    return p.parse_args()


def open_display(bus: int, addr: int, rotate: int) -> ssd1306:
    serial = i2c(port=bus, address=addr)
    return ssd1306(serial, rotate=rotate)


def draw_demo(devices: Sequence[ssd1306], start: float, font: ImageFont.ImageFont) -> None:
    elapsed = time.monotonic() - start
    for idx, dev in enumerate(devices):
        label = f"CEDE / SSD1306 #{idx + 1}"
        sub = f"{elapsed:5.1f}s"
        with canvas(dev) as draw:
            draw.rectangle(dev.bounding_box, outline="white", fill="black")
            draw.text((2, 0), label, font=font, fill="white")
            draw.text((2, 28), sub, font=font, fill="white")
            # Simple travelling pixel so activity is visible without fonts.
            x = int((elapsed * 24) % (dev.width - 4)) + 2
            draw.rectangle((x, 52, x + 4, 59), outline="white", fill="white")


def main() -> int:
    args = parse_args()
    if args.addr_a == args.addr_b:
        print(
            "error: --addr-a and --addr-b must differ on one bus (use SA0 / ADDR jumper).",
            file=sys.stderr,
        )
        return 2
    try:
        font = ImageFont.load_default()
        devices = [
            open_display(args.bus, args.addr_a, args.rotate),
            open_display(args.bus, args.addr_b, args.rotate),
        ]
    except OSError as e:
        print(
            "error: could not open I2C displays — check wiring, permissions (i2c group), "
            f"and addresses (i2cdetect -y {args.bus}): {e}",
            file=sys.stderr,
        )
        return 1

    period = 1.0 / max(args.fps, 0.25)
    start = time.monotonic()
    try:
        while True:
            draw_demo(devices, start, font)
            time.sleep(period)
    except KeyboardInterrupt:
        for dev in devices:
            dev.hide()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
