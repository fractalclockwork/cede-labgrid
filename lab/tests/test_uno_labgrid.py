"""Flash Uno via LabGrid and validate serial banner + digest.

Requires:
    - labgrid-coordinator running (in Docker orchestration-dev or standalone)
    - labgrid-exporter running on Pi with env/cede-pi-exporter.yaml
    - Uno connected to Pi USB

Run:
    pytest --lg-env env/remote.yaml lab/tests/test_uno_labgrid.py
"""

from __future__ import annotations

import pytest


@pytest.mark.labgrid
def test_uno_flash_and_validate(strategy, target):
    """Transition cede-uno through off -> flashed -> validated.

    This flashes the HEX artifact onto the Uno via avrdude, reads the serial
    banner, and asserts the digest= token matches the .digest sidecar file.
    """
    strategy.transition("validated")


@pytest.mark.labgrid
def test_uno_flash_only(strategy, target):
    """Flash Uno without serial validation."""
    strategy.transition("flashed")


@pytest.mark.labgrid
def test_uno_console(target):
    """Verify serial console access to Uno (no flash, just read existing output)."""
    from labgrid.protocol import ConsoleProtocol

    serial = target.get_active_driver(ConsoleProtocol)
    buf = serial.read(size=4096, timeout=5.0)
    text = buf.decode("utf-8", errors="replace") if buf else ""
    assert len(text) > 0, "No serial data received from Uno within 5s"
