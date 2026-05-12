"""I2C validation through LabGrid -- probe Pico (0x42) and Uno (0x43) via Pi gateway.

Uses the CedeI2CDriver bound to the cede-pi target, which runs i2cget
over SSH.  Validates TXS0108E level-shifter wiring and I2C bus connectivity.
Both Pico (RP2040) and Uno (ATmega328P) respond reliably when the level
shifter OE pin is properly tied to VCCA.

In practice MCUs will typically be I2C masters; this slave configuration
exists to validate the shared bus and level shifting from the Pi side.

Requires:
    - labgrid-coordinator + exporter running
    - Both Pico and Uno flashed with hello_lab (I2C slave enabled)
    - Pi connected to Pico/Uno via I2C bus 1 with TXS0108E (OE tied high)

Run:
    make lg-test-i2c
"""

from __future__ import annotations

import pytest

@pytest.fixture
def i2c(env):
    """Get the CedeI2CDriver from the cede-pi target (or 'main' in single-target env)."""
    pi = env.get_target("cede-pi")
    if pi is None:
        pi = env.get_target("main")
    if pi is None:
        pytest.skip("no cede-pi or main target in env")
    drv = pi.get_driver("CedeI2CDriver")
    pi.activate(drv)
    return drv


@pytest.fixture
def bus_speed(i2c) -> int | None:
    """Query the Pi's I2C bus clock rate (Hz) from config.txt."""
    return i2c.bus_speed_hz()


def _bus_speed_hint(bus_speed: int | None) -> str:
    """Return a diagnostic hint about the bus speed if available."""
    if bus_speed is None:
        return ""
    return (
        f" Pi I2C bus is configured at {bus_speed // 1000} kHz"
        f" (i2c_arm_baudrate={bus_speed})."
        f" If reads fail at this speed, check pull-up resistors,"
        f" TXS0108E level-shifter wiring, and bus capacitance."
        f" Try lowering to 100 kHz in /boot/firmware/config.txt."
    )


@pytest.mark.labgrid
def test_i2c_pico(i2c):
    """Read register 0 from Pico I2C slave at 0x42 -- expect 0xCE."""
    val = i2c.i2cget(addr=0x42, reg=0)
    assert val == 0xCE, f"Pico I2C reg 0 = {val:#x}, expected 0xCE"


@pytest.mark.labgrid
def test_i2c_uno(i2c, bus_speed):
    """Read register 0 from Uno I2C slave at 0x43 -- expect 0xCE."""
    try:
        val = i2c.i2cget(addr=0x43, reg=0)
    except RuntimeError as exc:
        pytest.fail(f"{exc}.{_bus_speed_hint(bus_speed)}")
    assert val == 0xCE, f"Uno I2C reg 0 = {val:#x}, expected 0xCE.{_bus_speed_hint(bus_speed)}"


@pytest.mark.labgrid
def test_i2c_both(i2c, bus_speed):
    """Both Pico and Uno respond on the same I2C bus."""
    pico_val = i2c.i2cget(addr=0x42, reg=0)
    assert pico_val == 0xCE, f"Pico: {pico_val:#x}"
    try:
        uno_val = i2c.i2cget(addr=0x43, reg=0)
    except RuntimeError as exc:
        pytest.fail(f"{exc}.{_bus_speed_hint(bus_speed)}")
    assert uno_val == 0xCE, f"Uno: {uno_val:#x}.{_bus_speed_hint(bus_speed)}"
