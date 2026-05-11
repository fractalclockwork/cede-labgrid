"""AvrdudeFlashDriver -- flash an Arduino Uno (ATmega328P) via avrdude.

Executes on the Pi gateway via the LabGrid exporter.  Mirrors the logic in
lab/pi/scripts/pi_flash_uno_avrdude.sh.
"""

from __future__ import annotations

import logging
import shlex

import attr
from labgrid.driver import Driver
from labgrid.factory import target_factory
from labgrid.protocol import CommandProtocol
from labgrid.step import step
from labgrid.util.managedfile import ManagedFile

from cede_labgrid.protocols.flash import FlashProtocol

logger = logging.getLogger(__name__)


@target_factory.reg_driver
@attr.s(eq=False)
class AvrdudeFlashDriver(Driver, FlashProtocol):
    """Flash an Uno HEX through the exporter's SSH/command channel.

    Bindings:
        command: CommandProtocol (SSHDriver or ShellDriver on the Pi)
        port:    USBSerialPort   (the Uno's serial device on the Pi)
    """

    bindings = {
        "command": CommandProtocol,
        "port": {"USBSerialPort", "NetworkSerialPort"},
    }

    image = attr.ib(default="uno_hex", validator=attr.validators.instance_of(str))
    programmer = attr.ib(default="arduino", validator=attr.validators.instance_of(str))
    partno = attr.ib(default="atmega328p", validator=attr.validators.instance_of(str))
    baudrate = attr.ib(default=115200, validator=attr.validators.instance_of(int))

    def _run(self, cmd: str, *, timeout: int = 30) -> tuple[list[str], list[str], int]:
        return self.command.run(cmd, timeout=timeout)

    def _resolve_image_path(self) -> str:
        return self.target.env.config.get_image_path(self.image)

    @Driver.check_active
    @step(args=["image"])
    def flash(self, *, image: str | None = None) -> None:
        """Transfer HEX to the Pi and flash via avrdude."""
        local_path = self._resolve_image_path() if image is None else image

        remote_hex = self._transfer_image(local_path)
        self._run_avrdude(remote_hex)

    def _transfer_image(self, local_path: str) -> str:
        """Sync the HEX to the exporter host via ManagedFile (content-addressed cache)."""
        mf = ManagedFile(local_path, self.port)
        mf.sync_to_resource()
        remote_path = mf.get_remote_path()
        logger.info("Image synced to %s on gateway", remote_path)
        return remote_path

    def _run_avrdude(self, remote_hex: str) -> None:
        serial_port = self.port.port
        cmd = (
            f"avrdude"
            f" -p {shlex.quote(self.partno)}"
            f" -c {shlex.quote(self.programmer)}"
            f" -P {shlex.quote(serial_port)}"
            f" -b {self.baudrate}"
            f" -D"
            f" -U flash:w:{shlex.quote(remote_hex)}:i"
        )
        logger.info("Running avrdude: %s", cmd)
        stdout, stderr, rc = self._run(cmd, timeout=60)
        if rc != 0:
            detail = " ".join(stderr) if stderr else "(no stderr)"
            raise RuntimeError(f"avrdude failed (rc={rc}): {detail}")
        logger.info("avrdude flash complete")
