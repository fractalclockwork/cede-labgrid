"""Flash Pico via LabGrid and validate serial banner + digest.

Requires:
    - labgrid-coordinator running (in Docker orchestration-dev or standalone)
    - labgrid-exporter running on Pi with env/cede-pi-exporter.yaml
    - Pico connected to Pi USB

Run:
    pytest --lg-env env/remote.yaml lab/tests/test_pico_labgrid.py
"""

from __future__ import annotations

import pytest


@pytest.mark.labgrid
def test_pico_flash_and_validate(strategy, target):
    """Transition cede-pico through off -> flashed -> validated.

    This flashes the UF2 artifact onto the Pico, reads the serial banner,
    and asserts the digest= token matches the .digest sidecar file.
    """
    strategy.transition("validated")


@pytest.mark.labgrid
def test_pico_flash_only(strategy, target):
    """Flash Pico without serial validation (useful for debugging flash issues)."""
    strategy.transition("flashed")


@pytest.mark.labgrid
def test_pico_console(target):
    """Verify serial console access to Pico (no flash, just read existing output)."""
    from labgrid.protocol import ConsoleProtocol

    serial = target.get_active_driver(ConsoleProtocol)
    buf = serial.read(size=4096, timeout=5.0)
    text = buf.decode("utf-8", errors="replace") if buf else ""
    assert len(text) > 0, "No serial data received from Pico within 5s"
