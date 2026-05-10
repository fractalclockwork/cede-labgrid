"""Uno-only hardware path: Docker build + avrdude flash + serial validate (unique digest per run).

Validates that the device reports ``digest-banner:`` matching the embedded id after flash.
Use ``pytest -s`` to see ``embedded-digest`` / ``expected-digest`` / ``digest-banner`` lines in the console.

  CEDE_RUN_HARDWARE_UNO=1 GATEWAY=pi@cede-pi.local uv run pytest -s lab/tests/test_hello_lab_hardware_uno_digest.py
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
    spec = importlib.util.spec_from_file_location("_cede_test_image_id_uno_hw", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.hardware
@pytest.mark.uno
def test_hello_lab_uno_only_build_flash_validate_unique_digest(repo_root: Path) -> None:
    if os.environ.get("CEDE_RUN_HARDWARE_UNO") != "1":
        pytest.skip("Set CEDE_RUN_HARDWARE_UNO=1 and attach Uno on the gateway (see module docstring).")

    if not shutil.which("docker"):
        pytest.skip("Docker required for uno-build")

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
        "pi-gateway-hello-lab-hardware-smoke-uno",
        f"GATEWAY={gateway}",
        f"CEDE_TEST_IMAGE_ID={run_id}",
    ]
    env = os.environ.copy()
    for key in ("GATEWAY_REPO_ROOT", "HEX", "PORT", "SKIP_SYNC", "UNO_VALIDATE_WAIT"):
        if key in os.environ:
            env[key] = os.environ[key]

    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        sys.stderr.write(combined)
    assert proc.returncode == 0, "pi-gateway-hello-lab-hardware-smoke-uno failed"
    assert run_id in combined, "expected CEDE_TEST_IMAGE_ID in make output"
    assert "digest-banner:" in combined, (
        "expected pi_validate_uno_serial digest-banner: line in make output (flash + correct firmware)"
    )
    # Surface the digest lines for `pytest -s` or CI logs.
    for line in combined.splitlines():
        if "digest-banner:" in line or "expected-digest:" in line or "embedded-digest" in line:
            print(line)
