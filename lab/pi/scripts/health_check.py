#!/usr/bin/env python3
"""Lightweight Pi gateway health: tools on PATH + optional lab serial resolution."""

from __future__ import annotations

import shutil
import subprocess
import sys

REQUIRED = ("picotool", "avrdude", "python3")


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

    print("health: ok (picotool, avrdude, python3 present)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
