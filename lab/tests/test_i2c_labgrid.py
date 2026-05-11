"""I2C validation through LabGrid -- probe Pico (0x42) and Uno (0x43) via Pi gateway.

Requires:
    - labgrid-coordinator + exporter running
    - Both Pico and Uno flashed with hello_lab (I2C slave enabled)
    - Pi connected to Pico/Uno via I2C bus 1 with level shifter

Run:
    pytest --lg-env env/remote.yaml lab/tests/test_i2c_labgrid.py
"""

from __future__ import annotations

import pytest


def _ssh_i2cget(target, bus: int, addr: int, reg: int) -> int:
    """Run i2cget on the Pi via the cede-pi SSHDriver and return the byte value."""
    from labgrid.protocol import CommandProtocol

    ssh = target.get_active_driver(CommandProtocol)
    cmd = f"sudo i2cget -y {bus} {addr:#x} {reg} b"
    stdout, stderr, rc = ssh.run(cmd, timeout=10)
    if rc != 0:
        detail = " ".join(stderr) if stderr else "(no stderr)"
        raise RuntimeError(f"i2cget failed (rc={rc}): {detail}")
    raw = stdout[0].strip() if stdout else ""
    return int(raw, 16)


@pytest.fixture
def pi_target(env):
    """Get the cede-pi target for SSH commands."""
    return env.get_target("cede-pi")


@pytest.mark.labgrid
def test_i2c_pico(pi_target):
    """Read register 0 from Pico I2C slave at 0x42 -- expect 0xCE."""
    val = _ssh_i2cget(pi_target, bus=1, addr=0x42, reg=0)
    assert val == 0xCE, f"Pico I2C reg 0 = {val:#x}, expected 0xCE"


@pytest.mark.labgrid
def test_i2c_uno(pi_target):
    """Read register 0 from Uno I2C slave at 0x43 -- expect 0xCE."""
    val = _ssh_i2cget(pi_target, bus=1, addr=0x43, reg=0)
    assert val == 0xCE, f"Uno I2C reg 0 = {val:#x}, expected 0xCE"


@pytest.mark.labgrid
def test_i2c_both(pi_target):
    """Both Pico and Uno respond on the same I2C bus."""
    pico_val = _ssh_i2cget(pi_target, bus=1, addr=0x42, reg=0)
    uno_val = _ssh_i2cget(pi_target, bus=1, addr=0x43, reg=0)
    assert pico_val == 0xCE, f"Pico: {pico_val:#x}"
    assert uno_val == 0xCE, f"Uno: {uno_val:#x}"
