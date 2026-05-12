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


@pytest.mark.labgrid
def test_i2c_pico(i2c):
    """Read register 0 from Pico I2C slave at 0x42 -- expect 0xCE."""
    val = i2c.i2cget(addr=0x42, reg=0)
    assert val == 0xCE, f"Pico I2C reg 0 = {val:#x}, expected 0xCE"


@pytest.mark.labgrid
def test_i2c_uno(i2c):
    """Read register 0 from Uno I2C slave at 0x43 -- expect 0xCE."""
    val = i2c.i2cget(addr=0x43, reg=0)
    assert val == 0xCE, f"Uno I2C reg 0 = {val:#x}, expected 0xCE"


@pytest.mark.labgrid
def test_i2c_both(i2c):
    """Both Pico and Uno respond on the same I2C bus."""
    pico_val = i2c.i2cget(addr=0x42, reg=0)
    uno_val = i2c.i2cget(addr=0x43, reg=0)
    assert pico_val == 0xCE, f"Pico: {pico_val:#x}"
    assert uno_val == 0xCE, f"Uno: {uno_val:#x}"
