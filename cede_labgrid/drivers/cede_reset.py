"""CedeResetDriver -- reset a CEDE MCU target to a known state.

Supports two reset methods:
- ``picotool``: issue ``picotool reboot`` via the exporter SSH (Pico)
- ``dtr``: toggle DTR on the serial port to trigger an Arduino reset (Uno)

Used by CedeStrategy in state_off to bring the target to a deterministic
starting point before flash or re-flash.
"""

from __future__ import annotations

import logging
import time

import attr
from labgrid.driver import Driver
from labgrid.factory import target_factory
from labgrid.protocol import CommandProtocol, ConsoleProtocol
from labgrid.step import step

logger = logging.getLogger(__name__)

RESET_METHODS = ("picotool", "dtr")


@target_factory.reg_driver
@attr.s(eq=False)
class CedeResetDriver(Driver):
    """Reset a CEDE MCU target via picotool reboot or serial DTR toggle.

    Bindings:
        command: CommandProtocol (SSHDriver -- optional, used for picotool)
        console: ConsoleProtocol (SerialDriver -- optional, used for DTR)
    """

    bindings = {
        "command": {CommandProtocol, None},
        "console": {ConsoleProtocol, None},
    }

    method = attr.ib(
        default="picotool",
        validator=attr.validators.in_(RESET_METHODS),
    )
    post_reset_delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    @Driver.check_active
    @step()
    def reset(self) -> None:
        """Reset the target MCU."""
        if self.method == "picotool":
            self._reset_picotool()
        elif self.method == "dtr":
            self._reset_dtr()
        time.sleep(self.post_reset_delay)

    def _reset_picotool(self) -> None:
        if self.command is None:
            logger.warning("No CommandProtocol bound; skipping picotool reset")
            return
        logger.info("Resetting Pico via picotool reboot")
        self.command.run("picotool reboot", timeout=10)

    def _reset_dtr(self) -> None:
        if self.console is None:
            logger.warning("No ConsoleProtocol bound; skipping DTR reset")
            return
        logger.info("Resetting Uno via DTR toggle")
        port = getattr(self.console, "serial", None)
        if port is not None and hasattr(port, "dtr"):
            port.dtr = False
            time.sleep(0.1)
            port.dtr = True
        else:
            logger.warning("Console does not expose serial.dtr; DTR toggle skipped")
