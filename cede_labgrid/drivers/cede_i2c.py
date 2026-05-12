"""CedeI2CDriver -- probe I2C slave registers on the Pi gateway via SSH.

Runs ``i2cget`` on the Pi through the LabGrid SSHDriver, providing a clean
driver interface for I2C bus validation in tests.  Configured in ``env/pi.yaml``.

The hello_lab firmware on each MCU exposes an I2C slave (Pico @0x42,
Uno @0x43) through a TXS0108E level shifter.  Ensure the shifter's OE
pin is tied to VCCA for reliable operation.
"""

from __future__ import annotations

import logging

import attr
from labgrid.driver import Driver
from labgrid.factory import target_factory
from labgrid.protocol import CommandProtocol
from labgrid.step import step

logger = logging.getLogger(__name__)


@target_factory.reg_driver
@attr.s(eq=False)
class CedeI2CDriver(Driver):
    """Probe I2C registers on the Pi gateway via i2cget over SSH.

    Bindings:
        command: CommandProtocol (SSHDriver on the Pi)
    """

    bindings = {"command": CommandProtocol}

    bus = attr.ib(default=1, validator=attr.validators.instance_of(int))

    @Driver.check_active
    @step()
    def i2cget(self, addr: int, reg: int) -> int:
        """Read a single byte from *addr* register *reg* on the configured bus."""
        cmd = f"sudo i2cget -y {self.bus} {addr:#x} {reg} b"
        logger.info("i2cget: %s", cmd)
        stdout, stderr, rc = self.command.run(cmd, timeout=10)
        if rc != 0:
            detail = " ".join(stderr) if stderr else "(no stderr)"
            raise RuntimeError(f"i2cget failed (rc={rc}): {detail}")
        raw = stdout[0].strip() if stdout else ""
        return int(raw, 16)

    @Driver.check_active
    @step()
    def i2cdetect(self) -> str:
        """Run i2cdetect and return the raw output table."""
        cmd = f"sudo i2cdetect -y {self.bus}"
        logger.info("i2cdetect: %s", cmd)
        stdout, stderr, rc = self.command.run(cmd, timeout=10)
        if rc != 0:
            detail = " ".join(stderr) if stderr else "(no stderr)"
            raise RuntimeError(f"i2cdetect failed (rc={rc}): {detail}")
        return "\n".join(stdout)
