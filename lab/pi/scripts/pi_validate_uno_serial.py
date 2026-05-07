#!/usr/bin/env python3
"""Open the Uno USB-serial device and confirm a banner line after reset. Run ON the gateway Pi."""

from __future__ import annotations

import argparse
import os
import select
import struct
import subprocess
import sys
import termios
import time


def _read_with_pyserial(port: str, baud: int, wait: float, expect_b: bytes) -> bytes:
    import serial  # type: ignore

    with serial.Serial(port, baud, timeout=0.2) as ser:
        ser.reset_input_buffer()
        ser.dtr = False
        time.sleep(0.05)
        ser.dtr = True
        deadline = time.monotonic() + wait
        buf = b""
        while time.monotonic() < deadline:
            buf += ser.read(4096)
            if expect_b in buf:
                break
            time.sleep(0.05)
    return buf


def _stty_raw(port: str, baud: int) -> None:
    subprocess.run(
        [
            "stty",
            "-F",
            port,
            "%d" % baud,
            "cs8",
            "-parenb",
            "-cstopb",
            "raw",
            "-echo",
            "min",
            "0",
            "time",
            "0",
        ],
        check=True,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        timeout=5,
    )


def _read_via_stty_ioctl(port: str, baud: int, wait: float, expect_b: bytes) -> bytes:
    """stty configures the line + Linux ioctl DTR (reset). Stdlib-only after stty."""

    try:
        _stty_raw(port, baud)
    except FileNotFoundError:
        raise OSError("`stty` not found — install coreutils") from None

    import fcntl

    TIOCMBIS = getattr(termios, "TIOCMBIS", 0x5416)
    TIOCMBIC = getattr(termios, "TIOCMBIC", 0x5417)
    TIOCM_DTR = getattr(termios, "TIOCM_DTR", 0x002)

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    try:
        try:
            termios.tcflush(fd, termios.TCIFLUSH)
        except termios.error:
            pass

        mask = struct.pack("I", TIOCM_DTR)
        fcntl.ioctl(fd, TIOCMBIC, mask)
        time.sleep(0.05)
        fcntl.ioctl(fd, TIOCMBIS, mask)

        deadline = time.monotonic() + wait
        buf = b""
        while time.monotonic() < deadline:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                buf += os.read(fd, 4096)
            if expect_b in buf:
                break
            time.sleep(0.02)
        return buf
    finally:
        os.close(fd)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("port", help="e.g. /dev/ttyACM0")
    p.add_argument(
        "--expect",
        default="CEDE hello_lab ok",
        help="substring that must appear from the board",
    )
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--wait", type=float, default=3.0, help="seconds to wait")
    args = p.parse_args()

    expect_b = args.expect.encode("utf-8")
    buf = b""

    try:
        buf = _read_with_pyserial(args.port, args.baud, args.wait, expect_b)
    except ImportError:
        try:
            buf = _read_via_stty_ioctl(args.port, args.baud, args.wait, expect_b)
        except OSError as e:
            print(f"error: serial read failed ({e}); try apt install python3-serial", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as e:
            print(f"error: stty failed ({e}); check PORT and gateway permissions", file=sys.stderr)
            return 1
    except OSError as e:
        print(f"error: could not open {args.port}: {e}", file=sys.stderr)
        return 1

    text = buf.decode("utf-8", errors="replace")
    if expect_b in buf:
        print("validate: ok (serial banner present)")
        print(text.strip())
        return 0

    print("validate: fail (expected banner not seen on serial)", file=sys.stderr)
    print(f"--- raw ({len(buf)} bytes) ---", file=sys.stderr)
    print(repr(text), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
