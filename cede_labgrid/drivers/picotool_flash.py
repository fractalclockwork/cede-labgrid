"""PicotoolFlashDriver -- flash a Raspberry Pi Pico via UF2 copy (BOOTSEL mass-storage).

Executes on the Pi gateway via the LabGrid exporter.  Mirrors the logic in
lab/pi/scripts/pi_flash_pico_auto.sh (picotool reboot -uf, wait for RPI-RP2,
cp UF2) but in Python so it integrates with the LabGrid driver lifecycle.
"""

from __future__ import annotations

import logging
import shlex
import time

import attr
from labgrid.driver import Driver
from labgrid.factory import target_factory
from labgrid.protocol import CommandProtocol
from labgrid.step import step
from labgrid.util.managedfile import ManagedFile

from cede_labgrid.protocols.flash import FlashProtocol

logger = logging.getLogger(__name__)

BOOTSEL_POLL_INTERVAL = 0.4
BOOTSEL_TIMEOUT_DEFAULT = 15


@target_factory.reg_driver
@attr.s(eq=False)
class PicotoolFlashDriver(Driver, FlashProtocol):
    """Flash a Pico UF2 through the exporter's SSH/command channel.

    Bindings:
        command: CommandProtocol (SSHDriver or ShellDriver on the Pi)
        port:    USBSerialPort (Pico serial; used for ManagedFile transfer)
    """

    bindings = {
        "command": CommandProtocol,
        "port": {"USBSerialPort", "NetworkSerialPort"},
    }

    image = attr.ib(default="pico_uf2", validator=attr.validators.instance_of(str))
    bootsel_timeout = attr.ib(default=BOOTSEL_TIMEOUT_DEFAULT, validator=attr.validators.instance_of(int))

    def _run(self, cmd: str, *, timeout: int = 30) -> tuple[list[str], list[str], int]:
        return self.command.run(cmd, timeout=timeout)

    def _resolve_image_path(self) -> str:
        return self.target.env.config.get_image_path(self.image)

    @Driver.check_active
    @step(args=["image"])
    def flash(self, *, image: str | None = None) -> None:
        """Transfer UF2 to the Pi and flash the Pico via picotool."""
        local_path = self._resolve_image_path() if image is None else image

        remote_path = self._transfer_image(local_path)
        self._picotool_load(remote_path)

    def _transfer_image(self, local_path: str) -> str:
        """Sync the UF2 to the exporter host via ManagedFile (content-addressed cache)."""
        mf = ManagedFile(local_path, self.port)
        mf.sync_to_resource()
        remote_path = mf.get_remote_path()
        logger.info("Image synced to %s on gateway", remote_path)
        return remote_path

    def _picotool_load(self, remote_uf2: str) -> None:
        """Flash UF2 via picotool, handling the BOOTSEL reboot + load sequence.

        Strategy: try ``picotool load -f -v -x`` first (atomic reboot+load).
        If that fails (dwc_otg re-enumeration issues on Pi 3B), fall back to a
        two-step approach: ``picotool reboot -uf`` then poll with
        ``picotool load -v -x`` until the device appears in BOOTSEL.
        """
        uf2 = shlex.quote(remote_uf2)

        stdout, stderr, rc = self._run(f"picotool load -f -v -x {uf2}", timeout=30)
        if rc == 0:
            logger.info("picotool load -f succeeded")
            time.sleep(2)
            return

        logger.warning("picotool load -f failed (rc=%d); trying two-step reboot+load", rc)
        self._run("picotool reboot -uf 2>/dev/null || true", timeout=10)
        time.sleep(1)

        deadline = time.monotonic() + self.bootsel_timeout
        while time.monotonic() < deadline:
            stdout, stderr, rc = self._run(f"picotool load -v -x {uf2}", timeout=20)
            if rc == 0:
                logger.info("picotool load succeeded after BOOTSEL reboot")
                time.sleep(2)
                return
            time.sleep(BOOTSEL_POLL_INTERVAL)

        raise RuntimeError(
            f"picotool load failed after {self.bootsel_timeout}s. "
            "Pico may not have entered BOOTSEL mode."
        )
