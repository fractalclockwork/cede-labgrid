#!/usr/bin/env python3
"""Emit a one-line CEDE_IMAGE_ID / digest token unique to this process invocation.

Safe for hello_lab CMake + Uno gen_cede_image_id.sh ([A-Za-z0-9._-]+).
Used by: make pi-gateway-hello-lab-hardware-smoke / …-uno / …-pico; pytest CEDE_RUN_HARDWARE_FULL=1, CEDE_RUN_HARDWARE_UNO=1, CEDE_RUN_HARDWARE_PICO=1.
"""

from __future__ import annotations

import secrets
import time


def make_test_image_id() -> str:
    """Monotonic wall clock + random suffix so two calls in the same second still differ."""
    return f"t{int(time.time())}_{secrets.token_hex(4)}"


def main() -> None:
    print(make_test_image_id(), end="")


if __name__ == "__main__":
    main()
