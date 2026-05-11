"""PicotoolFlashDriver -- flash a Raspberry Pi Pico via UF2 copy (BOOTSEL mass-storage).

Executes on the Pi gateway via the LabGrid exporter.  Mirrors the logic in
lab/pi/scripts/pi_flash_pico_auto.sh (picotool reboot -uf, wait for RPI-RP2,
cp UF2) but in Python so it integrates with the LabGrid driver lifecycle.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
import time

import attr
from labgrid.driver import Driver
from labgrid.factory import target_factory
from labgrid.protocol import CommandProtocol
from labgrid.step import step

logger = logging.getLogger(__name__)

BOOTSEL_POLL_INTERVAL = 0.4
BOOTSEL_TIMEOUT_DEFAULT = 15


@target_factory.reg_driver
@attr.s(eq=False)
class PicotoolFlashDriver(Driver):
    """Flash a Pico UF2 through the exporter's SSH/command channel.

    Bindings:
        command: CommandProtocol (SSHDriver or ShellDriver on the Pi)
    """

    bindings = {"command": CommandProtocol}

    image = attr.ib(default="pico_uf2", validator=attr.validators.instance_of(str))
    bootsel_timeout = attr.ib(default=BOOTSEL_TIMEOUT_DEFAULT, validator=attr.validators.instance_of(int))

    def _run(self, cmd: str, *, timeout: int = 30) -> tuple[list[str], list[str], int]:
        return self.command.run(cmd, timeout=timeout)

    def _resolve_image_path(self) -> str:
        return self.target.env.config.get_image_path(self.image)

    @Driver.check_active
    @step(args=["image"])
    def flash(self, *, image: str | None = None) -> None:
        """Transfer UF2 to the Pi and copy it to the Pico in BOOTSEL mode."""
        local_path = self._resolve_image_path() if image is None else image

        remote_path = f"/tmp/{local_path.rsplit('/', 1)[-1]}"
        self._transfer_image(local_path, remote_path)
        self._enter_bootsel()
        self._wait_and_copy_uf2(remote_path)

    def _transfer_image(self, local_path: str, remote_path: str) -> None:
        logger.info("Transferring %s -> %s on gateway", local_path, remote_path)
        self.command.put(local_path, remote_path)

    def _enter_bootsel(self) -> None:
        """Try picotool reboot -uf to put the Pico into BOOTSEL mode."""
        stdout, stderr, rc = self._run("command -v picotool && picotool help 2>&1 | grep -q reboot && echo ok || echo no")
        has_reboot = any("ok" in line for line in stdout)

        if has_reboot:
            logger.info("Entering BOOTSEL via picotool reboot -uf")
            self._run("picotool reboot -uf", timeout=10)
            time.sleep(1)
        else:
            logger.info("picotool reboot unavailable; assuming Pico is already in BOOTSEL")

    def _wait_and_copy_uf2(self, remote_uf2: str) -> None:
        """Poll for RPI-RP2 mount/partition and copy the UF2."""
        deadline = time.monotonic() + self.bootsel_timeout

        while time.monotonic() < deadline:
            mount = self._find_rpi_rp2_mount()
            if mount:
                logger.info("RPI-RP2 mounted at %s, copying UF2", mount)
                cmd = f"cp {shlex.quote(remote_uf2)} {shlex.quote(mount)}/ && sync"
                stdout, stderr, rc = self._run(cmd, timeout=30)
                if rc != 0:
                    raise RuntimeError(
                        f"UF2 copy failed (rc={rc}): {' '.join(stderr)}"
                    )
                logger.info("UF2 flash complete; Pico should reboot")
                return

            part = self._resolve_rpi_rp2_partition()
            if part:
                logger.info("RPI-RP2 partition at %s (no mount), raw copy", part)
                cmd = (
                    f"cp {shlex.quote(remote_uf2)} {shlex.quote(part)} 2>/dev/null "
                    f"|| sudo -n cp {shlex.quote(remote_uf2)} {shlex.quote(part)}"
                )
                stdout, stderr, rc = self._run(f"{cmd} && sync", timeout=30)
                if rc != 0:
                    raise RuntimeError(
                        f"Raw UF2 write failed (rc={rc}): {' '.join(stderr)}"
                    )
                logger.info("Raw UF2 write complete; Pico should reboot")
                return

            time.sleep(BOOTSEL_POLL_INTERVAL)

        raise RuntimeError(
            f"RPI-RP2 volume did not appear within {self.bootsel_timeout}s. "
            "Hold BOOTSEL while connecting Pico USB."
        )

    def _find_rpi_rp2_mount(self) -> str | None:
        stdout, _, rc = self._run(
            "for d in /media/*/RPI-RP2 /run/media/*/RPI-RP2; do "
            '[ -d "$d" ] && echo "$d" && exit 0; done; exit 1',
            timeout=5,
        )
        if rc == 0 and stdout:
            return stdout[0].strip()
        return None

    def _resolve_rpi_rp2_partition(self) -> str | None:
        stdout, _, rc = self._run(
            '[ -e /dev/disk/by-label/RPI-RP2 ] && readlink -f /dev/disk/by-label/RPI-RP2',
            timeout=5,
        )
        if rc == 0 and stdout:
            return stdout[0].strip()
        return None
