"""End-to-end hello_lab on real hardware: unique digest per run proves firmware is not stale.

Requires Docker (``lab/docker`` pico-build + uno-build), SSH to ``GATEWAY``, and Pico + Uno USB on the Pi.

Run::

  CEDE_RUN_HARDWARE_FULL=1 GATEWAY=pi@cede-pi.local uv run pytest -q lab/tests/test_hello_lab_hardware_full.py

Or from the repo root (same effect via Makefile)::

  make pi-gateway-hello-lab-hardware-smoke GATEWAY=pi@cede-pi.local
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _load_test_image_id_mod(repo_root: Path):
    path = repo_root / "lab" / "pi" / "scripts" / "cede_test_image_id.py"
    spec = importlib.util.spec_from_file_location("_cede_test_image_id_hw", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.hardware
def test_hello_lab_build_flash_validate_unique_digest_per_run(repo_root: Path) -> None:
    if os.environ.get("CEDE_RUN_HARDWARE_FULL") != "1":
        pytest.skip("Set CEDE_RUN_HARDWARE_FULL=1 and attach Pico+Uno on the gateway (see module docstring).")

    if not shutil.which("docker"):
        pytest.skip("Docker required for pico-build / uno-build")

    if not shutil.which("make"):
        pytest.skip("make required")

    gateway = os.environ.get("GATEWAY", "pi@cede-pi.local")
    m = _load_test_image_id_mod(repo_root)
    run_id = m.make_test_image_id()

    cmd = [
        "make",
        "--no-print-directory",
        "-C",
        str(repo_root),
        "pi-gateway-hello-lab-hardware-smoke",
        f"GATEWAY={gateway}",
        f"CEDE_TEST_IMAGE_ID={run_id}",
    ]
    env = os.environ.copy()
    # Propagate optional flash paths / ports from the environment running pytest.
    for key in (
        "GATEWAY_REPO_ROOT",
        "UF2",
        "HEX",
        "PORT",
        "UNO_PORT",
        "SKIP_SYNC",
        "PICO_BOOTSEL_ONLY",
        "PICO_WAIT_MOUNT",
        "PICO_VALIDATE_WAIT",
        "UNO_VALIDATE_WAIT",
    ):
        if key in os.environ:
            env[key] = os.environ[key]

    # Long-running: Docker builds + two flashes + serial validation.
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=7200)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
    assert proc.returncode == 0, "pi-gateway-hello-lab-hardware-smoke failed (stdout/stderr printed above)"
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert run_id in combined, "expected unique CEDE_TEST_IMAGE_ID in make log (proves this run's digest was used)"
    assert combined.count("digest-banner:") >= 2, (
        "expected digest-banner: from both Pico and Uno serial validators after flash"
    )
    for line in combined.splitlines():
        if "digest-banner:" in line or "expected-digest:" in line or "embedded-digest" in line:
            print(line)
