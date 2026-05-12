#!/usr/bin/env python3
"""Dual SSD1306 cartoon eyes on the Raspberry Pi (blink, conjugate gaze, vergence, pupil).

Run from repo on gateway: ``python3 main.py`` with cwd anywhere — adjusts sys.path to this folder.

Requires: pip install -r requirements.txt (on the Pi).
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from PIL import Image

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dirty_stats import RollingDirtyStats, pixel_change_fraction
from eyes_anim import EyeAnimator
from eyes_draw import render_eye

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306


def _contrast_arg(value: str) -> int:
    """SSD1306 contrast register (0 = dimmest, 255 = brightest)."""
    try:
        v = int(value, 0)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e
    if not 0 <= v <= 255:
        raise argparse.ArgumentTypeError("contrast must be between 0 and 255")
    return v


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bus", type=int, default=1, help="Linux I2C bus (default 1)")
    p.add_argument(
        "--addr-left",
        type=lambda x: int(x, 0),
        default=0x3C,
        metavar="ADDR",
        help="7-bit address for physical left panel (default 0x3C)",
    )
    p.add_argument(
        "--addr-right",
        type=lambda x: int(x, 0),
        default=0x3D,
        metavar="ADDR",
        help="7-bit address for physical right panel (default 0x3D)",
    )
    p.add_argument("--rotate", type=int, default=0, choices=(0, 1, 2, 3))
    p.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Target loop rate (caps sleep; hardware may be slower). Default 30.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for repeatable animation (default: nondeterministic)",
    )
    p.add_argument(
        "--stats-interval",
        type=int,
        default=0,
        metavar="N",
        help="Every N frames print rolling mean dirty %% (0 = off)",
    )
    p.add_argument(
        "--contrast-left",
        type=_contrast_arg,
        default=255,
        metavar="0-255",
        help="SSD1306 contrast for the physical left panel (default 255 = max)",
    )
    p.add_argument(
        "--contrast-right",
        type=_contrast_arg,
        default=255,
        metavar="0-255",
        help="SSD1306 contrast for the physical right panel (default 255 = max)",
    )
    return p.parse_args()


def open_display(bus: int, addr: int, rotate: int, contrast: int) -> ssd1306:
    serial = i2c(port=bus, address=addr)
    dev = ssd1306(serial, rotate=rotate)
    dev.contrast(contrast)
    return dev


def main() -> int:
    args = parse_args()
    if args.addr_left == args.addr_right:
        print("error: --addr-left and --addr-right must differ", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)

    try:
        dev_left = open_display(
            args.bus, args.addr_left, args.rotate, args.contrast_left
        )
        dev_right = open_display(
            args.bus, args.addr_right, args.rotate, args.contrast_right
        )
    except OSError as e:
        print(
            f"error: could not open I2C displays (i2cdetect -y {args.bus}): {e}",
            file=sys.stderr,
        )
        return 1

    w, h = dev_left.width, dev_right.height
    if dev_right.width != w or dev_right.height != h:
        print("error: left and right panels must match dimensions", file=sys.stderr)
        return 2

    animator = EyeAnimator(rng)
    period = 1.0 / max(args.fps, 1.0)

    prev_left: Image.Image | None = None
    prev_right: Image.Image | None = None
    rolling = RollingDirtyStats(window=120)
    frame_i = 0
    last_t = time.monotonic()

    try:
        while True:
            t0 = time.monotonic()
            dt_raw = t0 - last_t
            last_t = t0
            dt = max(1e-6, min(dt_raw, 0.25))
            pose = animator.advance(dt)

            img_l = render_eye(w, h, pose, eye_side="left")
            img_r = render_eye(w, h, pose, eye_side="right")

            dev_left.display(img_l.convert(dev_left.mode))
            dev_right.display(img_r.convert(dev_right.mode))

            if args.stats_interval > 0 and prev_left is not None and prev_right is not None:
                fl = pixel_change_fraction(prev_left, img_l)
                fr = pixel_change_fraction(prev_right, img_r)
                rolling.push_fraction((fl + fr) * 0.5)
                frame_i += 1
                if frame_i % args.stats_interval == 0:
                    m = rolling.mean_fraction()
                    print(
                        f"dirty frac L={fl:.3f} R={fr:.3f} rolling_mean={m:.3f}",
                        flush=True,
                    )

            prev_left = img_l
            prev_right = img_r

            elapsed = time.monotonic() - t0
            slack = period - elapsed
            if slack > 0:
                time.sleep(slack)
    except KeyboardInterrupt:
        for dev in (dev_left, dev_right):
            try:
                dev.hide()
            except OSError:
                pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
