"""PicotoolFlashDriver -- flash a Raspberry Pi Pico via picotool.

Executes on the Pi gateway via the LabGrid exporter.  Handles the Pi 3B
``dwc_otg`` USB controller quirk where USB re-enumeration fails unless
the USB subsystem is explicitly poked (usbreset / hub rebind).

Flash sequence:
  1. ``usbreset`` the running Pico to fix the USB interface
  2. ``picotool load -f -v -x`` (atomic reboot + flash + verify + execute)
  3. If that fails: ``picotool reboot -u -f`` → ``usbreset`` BOOTSEL device
     → ``picotool load -v -x``
  4. After flash: rebind the parent USB hub port to force clean re-enumeration
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

BOOTSEL_TIMEOUT_DEFAULT = 20
POST_FLASH_SETTLE = 3
PICO_VID = "2e8a"
PICO_VID_PID_APP = "2e8a:000a"
PICO_VID_PID_BOOT = "2e8a:0003"


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
        try:
            return self.command.run(cmd, timeout=timeout)
        except UnicodeDecodeError:
            logger.debug("Non-UTF-8 output from: %s (treating as failure)", cmd)
            return [], [], 1

    def _resolve_image_path(self) -> str:
        return self.target.env.config.get_image_path(self.image)

    @Driver.check_active
    @step(args=["image"])
    def flash(self, *, image: str | None = None) -> None:
        """Transfer UF2 to the Pi and flash the Pico via picotool."""
        local_path = self._resolve_image_path() if image is None else image

        remote_path = self._transfer_image(local_path)
        self._flash_pico(remote_path)

    def _transfer_image(self, local_path: str) -> str:
        """Sync the UF2 to the exporter host via ManagedFile (content-addressed cache)."""
        mf = ManagedFile(local_path, self.port)
        mf.sync_to_resource()
        remote_path = mf.get_remote_path()
        logger.info("Image synced to %s on gateway", remote_path)
        return remote_path

    def _usbreset(self, vid_pid: str) -> None:
        """Issue ``usbreset`` for the given VID:PID to fix dwc_otg USB state.

        The usbreset may report "failed" but still fixes the USB interface
        internally — this is expected on dwc_otg.
        """
        logger.debug("usbreset %s", vid_pid)
        self._run(f"sudo usbreset {vid_pid} 2>/dev/null || true", timeout=10)
        time.sleep(2)

    def _find_pico_usb_port(self) -> str | None:
        """Find the sysfs USB port identifier for the Pico (e.g. '1-1.4.1').

        Walks /sys/bus/usb/devices/*/idVendor looking for VID 2e8a.
        """
        stdout, _, rc = self._run(
            f"for d in /sys/bus/usb/devices/*/idVendor; do "
            f"dir=$(dirname $d); "
            f"[ \"$(cat $dir/idVendor 2>/dev/null)\" = '{PICO_VID}' ] && "
            f"basename $dir && break; done",
            timeout=5,
        )
        if rc == 0 and stdout and stdout[0].strip():
            return stdout[0].strip()
        return None

    def _rebind_parent_hub(self, usb_port: str) -> None:
        """Unbind and rebind the parent USB hub to force clean re-enumeration.

        On Pi 3B dwc_otg, the Pico's USB VID:PID can be stale after
        a picotool-triggered reboot.  Rebinding the parent hub port
        forces the controller to re-enumerate all child devices.
        """
        parts = usb_port.rsplit(".", 1)
        if len(parts) != 2:
            logger.warning("Cannot determine parent hub for USB port %s", usb_port)
            return

        parent_hub = parts[0]
        logger.info("Rebinding parent hub %s to force USB re-enumeration", parent_hub)

        self._run(
            f"echo '{usb_port}' | sudo tee /sys/bus/usb/drivers/usb/unbind "
            f"2>/dev/null || true",
            timeout=5,
        )
        time.sleep(1)
        self._run(
            f"echo '{parent_hub}' | sudo tee /sys/bus/usb/drivers/usb/unbind "
            f"2>/dev/null || true",
            timeout=5,
        )
        time.sleep(1)
        self._run(
            f"echo '{parent_hub}' | sudo tee /sys/bus/usb/drivers/usb/bind "
            f"2>/dev/null || true",
            timeout=5,
        )
        time.sleep(5)

    def _flash_pico(self, remote_uf2: str) -> None:
        """Flash UF2 using a dwc_otg-safe sequence.

        On Pi 4/5 the simple ``picotool load -f -v -x`` works fine.
        On Pi 3B the dwc_otg controller breaks USB re-enumeration, so we
        must: usbreset → reboot to BOOTSEL → usbreset → picotool load →
        rebind parent hub.
        """
        uf2 = shlex.quote(remote_uf2)
        usb_port = self._find_pico_usb_port()

        # Fix USB interface state before attempting picotool commands
        self._usbreset(PICO_VID_PID_APP)

        # Fast path: atomic picotool load (works on Pi 4/5, sometimes on 3B)
        stdout, stderr, rc = self._run(
            f"sudo picotool load -f -v -x {uf2}", timeout=20,
        )
        if rc == 0:
            logger.info("picotool load -f succeeded (fast path)")
            if usb_port:
                self._rebind_parent_hub(usb_port)
            else:
                time.sleep(POST_FLASH_SETTLE)
            return

        logger.warning(
            "picotool load -f failed (rc=%d); using BOOTSEL reboot sequence", rc,
        )

        # dwc_otg recovery path:
        # 1. usbreset to fix the USB interface after the failed load attempt
        self._usbreset(PICO_VID_PID_APP)

        # 2. Reboot into BOOTSEL
        logger.info("Rebooting Pico into BOOTSEL mode")
        self._run("sudo picotool reboot -u -f 2>&1 || true", timeout=10)
        time.sleep(3)

        # 3. usbreset the BOOTSEL device to stabilize its USB interface
        self._usbreset(PICO_VID_PID_BOOT)

        # 4. Flash via picotool load (no -f since we're already in BOOTSEL)
        deadline = time.monotonic() + self.bootsel_timeout
        while time.monotonic() < deadline:
            stdout, stderr, rc = self._run(
                f"sudo picotool load -v -x {uf2}", timeout=30,
            )
            if rc == 0:
                logger.info("picotool load succeeded via BOOTSEL path")
                # Re-enumerate the USB device back to application mode
                usb_port = self._find_pico_usb_port()
                if usb_port:
                    self._rebind_parent_hub(usb_port)
                else:
                    time.sleep(POST_FLASH_SETTLE)
                return
            time.sleep(1)

        raise RuntimeError(
            f"picotool load failed after {self.bootsel_timeout}s. "
            "Pico did not respond in BOOTSEL mode. "
            "Check USB connection; on Pi 3B ensure 'usbreset' is installed."
        )
