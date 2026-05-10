"""Scaffold for Hello Lab Tests 3–7 (hardware/Pi); most remain stubs.

Full build+flash+unique-digest validation: ``CEDE_RUN_HARDWARE_FULL=1`` and
``lab/tests/test_hello_lab_hardware_full.py`` or ``make pi-gateway-hello-lab-hardware-smoke``.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.hardware
@pytest.mark.pi_gateway
def test_flash_pico_from_pi() -> None:
    pytest.skip("Implement on Pi with picotool + deployed UF2 (DESIGN §9 Test 3)")


@pytest.mark.hardware
@pytest.mark.pi_gateway
def test_flash_uno_from_pi() -> None:
    pytest.skip("Implement on Pi with avrdude (DESIGN §9 Test 4)")


@pytest.mark.hardware
@pytest.mark.pi_gateway
def test_serial_pico_echo() -> None:
    pytest.skip("Serial round-trip Pi↔Pico (DESIGN §9 Test 5)")


@pytest.mark.hardware
@pytest.mark.pi_gateway
def test_serial_uno_echo() -> None:
    pytest.skip("Serial round-trip Pi↔Uno (DESIGN §9 Test 6)")


@pytest.mark.hardware
@pytest.mark.pi_gateway
def test_i2c_matrix_enabled_pairs() -> None:
    pytest.skip("Use make pi-gateway-validate-i2c-from-lab or CEDE_RUN_HARDWARE_FULL + test_hello_lab_hardware_full")


def test_ci_has_no_hardware_marker_by_default() -> None:
    """CI runs without hardware; integration tests stay skipped."""
    assert os.environ.get("CEDE_FORCE_HARDWARE") is None
